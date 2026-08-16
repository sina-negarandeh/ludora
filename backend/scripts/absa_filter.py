import os
import sys
import pandas as pd
import hashlib
import argparse
import re
import requests
from pathlib import Path
import fasttext

def download_fasttext_model(model_path):
    if not os.path.exists(model_path):
        print("Downloading fastText language model...")
        url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
        r = requests.get(url, allow_redirects=True)
        with open(model_path, 'wb') as f:
            f.write(r.content)
        print("Downloaded.")

def compute_quality_score(text, ft_model):
    if not isinstance(text, str) or not text.strip():
        return 0.0
        
    text = text.strip()
    words = text.split()
    
    # 1. Language Score
    # fastText expects text without newlines
    clean_text = text.replace('\n', ' ')
    langs, probs = ft_model.predict(clean_text, k=1)
    if langs[0] != '__label__en':
        language_score = 0.0
    else:
        language_score = probs[0]
        
    if language_score < 0.5:
        return 0.0 # Strict drop for non-English
        
    # 2. Length Score (normalize up to 100 words)
    length_score = min(len(words) / 100.0, 1.0)
    
    # 3. Spam Penalty (excessive repeated characters)
    # e.g., "soooo" or "!!!!!"
    spam_penalty = 0.0
    if re.search(r'(.)\1{4,}', text):
        spam_penalty = 0.5
        
    # 4. Aspect Signal Score (heuristic for game terms)
    # Give a tiny boost if it contains common game words
    game_words = {'rulebook', 'setup', 'cards', 'component', 'components', 'theme', 'mechanic', 'player', 'time', 'luck', 'balance'}
    text_lower = set(word.lower() for word in words)
    aspect_signal = min(len(text_lower.intersection(game_words)) * 0.1, 0.4)
    
    score = language_score + length_score + aspect_signal - spam_penalty
    return max(score, 0.0)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-ids', nargs='+', type=int, required=True, help='BGG IDs to process')
    args = parser.parse_args()
    
    base_dir = os.path.join(os.path.dirname(__file__), '../../data/processed')
    reviews_path = os.path.join(base_dir, 'master_reviews.csv')
    
    ft_model_path = os.path.join(os.path.dirname(__file__), '../../data/models/lid.176.ftz')
    os.makedirs(os.path.dirname(ft_model_path), exist_ok=True)
    download_fasttext_model(ft_model_path)
    
    print("Loading fastText model...")
    ft_model = fasttext.load_model(ft_model_path)
    
    print(f"Loading reviews for games {args.game_ids}...")
    
    # In a massive dataset, we would chunk. For pilot game IDs, we can filter while loading in chunks
    chunk_size = 500000
    filtered_rows = []
    
    total_scanned = 0
    
    # Deduplication Set
    seen_hashes = set()
    duplicates_skipped = 0
    
    for chunk in pd.read_csv(reviews_path, chunksize=chunk_size, dtype={'game_id': 'int32'}):
        # Keep only our pilot games
        pilot_chunk = chunk[chunk['game_id'].isin(args.game_ids)].copy()
        
        for _, row in pilot_chunk.iterrows():
            total_scanned += 1
            text = str(row['comment'])
            
            if not text or text.strip() == 'nan':
                continue
                
            # Text Hashing
            norm_text = text.lower().strip()
            text_hash = hashlib.md5(norm_text.encode('utf-8')).hexdigest()
            
            if text_hash in seen_hashes:
                duplicates_skipped += 1
                continue
            seen_hashes.add(text_hash)
            
            q_score = compute_quality_score(text, ft_model)
            is_eligible = q_score >= 0.6
            
            filtered_rows.append({
                'user_id': row['user_id'],
                'game_id': row['game_id'],
                'rating': row.get('rating', None),
                'comment': text,
                'quality_score': round(q_score, 3),
                'is_absa_eligible': is_eligible
            })
            
    df_out = pd.DataFrame(filtered_rows)
    print(f"\nScanning complete.")
    print(f"Scanned {total_scanned} reviews for pilot games.")
    print(f"Skipped {duplicates_skipped} exact duplicates.")
    
    eligible_count = df_out['is_absa_eligible'].sum() if not df_out.empty else 0
    print(f"Found {eligible_count} reviews eligible for ABSA (Quality >= 0.6).")
    
    out_path = os.path.join(base_dir, 'pilot_absa_filtered.csv')
    df_out.to_csv(out_path, index=False)
    print(f"Saved ABSA filter dataset to {out_path}")

if __name__ == "__main__":
    main()
