import os
import sys
import time
import argparse
import re
from datetime import datetime
from pathlib import Path
import requests

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import fasttext
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent.resolve()))
from sqlalchemy import text
from app.database.session import SessionLocal
from app.database.models import Game, Review

# The 22 Aspects strictly allowed
TAXONOMY = [
    "Gameplay", "Mechanics", "Strategy", "Theme", "Immersion", "Replayability", 
    "Components", "Artwork", "Production Quality", "Rulebook", "Setup", "Teardown", 
    "Learning Curve", "Complexity", "Downtime", "Player Interaction", "Balance", 
    "Luck", "Player Count", "Solo Play", "Game Length", "Value"
]

def download_fasttext_model(model_path):
    if not os.path.exists(model_path):
        print("Downloading fastText language model...")
        url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
        r = requests.get(url, allow_redirects=True)
        with open(model_path, 'wb') as f:
            f.write(r.content)
        print("Downloaded.")

def compute_quality_score(text_val, ft_model):
    if not isinstance(text_val, str) or not text_val.strip():
        return 0.0
        
    text_val = text_val.strip()
    words = text_val.split()
    
    clean_text = text_val.replace('\n', ' ')
    langs, probs = ft_model.predict(clean_text, k=1)
    if langs[0] != '__label__en':
        language_score = 0.0
    else:
        language_score = probs[0]
        
    if language_score < 0.5:
        return 0.0
        
    length_score = min(len(words) / 100.0, 1.0)
    
    spam_penalty = 0.0
    if re.search(r'(.)\1{4,}', text_val):
        spam_penalty = 0.5
        
    game_words = {'rulebook', 'setup', 'cards', 'component', 'components', 'theme', 'mechanic', 'player', 'time', 'luck', 'balance'}
    text_lower = set(word.lower() for word in words)
    aspect_signal = min(len(text_lower.intersection(game_words)) * 0.1, 0.4)
    
    score = language_score + length_score + aspect_signal - spam_penalty
    return max(score, 0.0)

def extract_sentence(text_val, aspect):
    """Fallback to extract the sentence containing the aspect."""
    # Simple split by punctuation
    sentences = re.split(r'(?<=[.!?]) +', text_val.replace('\n', ' '))
    for s in sentences:
        if aspect.lower() in s.lower():
            return s.strip()
    return ""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20, help='Number of eligible reviews to process')
    parser.add_argument('--game_id', type=int, default=224517, help='BGG ID for the game to test (default: Brass Birmingham)')
    args = parser.parse_args()
    
    base_dir = os.path.dirname(__file__)
    ft_model_path = os.path.join(base_dir, '../../data/models/lid.176.ftz')
    os.makedirs(os.path.dirname(ft_model_path), exist_ok=True)
    download_fasttext_model(ft_model_path)
    
    print("Loading fastText model for quality filtering...")
    ft_model = fasttext.load_model(ft_model_path)
    
    db = SessionLocal()
    
    print(f"Fetching reviews for Game ID {args.game_id}...")
    # Fetch all reviews for this game and filter locally
    reviews = db.query(Review).filter(Review.game_id == args.game_id).yield_per(1000)
    
    eligible_reviews = []
    for r in reviews:
        if r.comment:
            q_score = compute_quality_score(r.comment, ft_model)
            if q_score >= 0.6:
                eligible_reviews.append(r)
                if len(eligible_reviews) >= args.limit:
                    break
                    
    print(f"Found {len(eligible_reviews)} highly eligible reviews out of limit {args.limit}.")
    if not eligible_reviews:
        print("No eligible reviews found.")
        return

    # Load HF Model
    device = torch.device("mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu"))
    print(f"Loading DeBERTa ABSA model on device: {device} ...")
    
    model_name = "yangheng/deberta-v3-large-absa-v1.1"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name).to(device)
    model.eval()

    # The mapping is usually: 0: Negative, 1: Neutral, 2: Positive
    label_map = {0: "negative", 1: "neutral", 2: "positive"}

    print("\nStarting extraction...")
    total_aspects_found = 0
    start_time = time.time()
    
    with torch.no_grad():
        for r in eligible_reviews:
            text_val = r.comment
            
            # Create a batch for all 22 aspects
            texts = [text_val] * len(TAXONOMY)
            aspects = TAXONOMY
            
            inputs = tokenizer(texts, aspects, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1)
            
            batch_params = []
            
            for i, aspect in enumerate(TAXONOMY):
                prob_neg = probs[i][0].item()
                prob_neu = probs[i][1].item()
                prob_pos = probs[i][2].item()
                
                # Determine winner
                winner_idx = probs[i].argmax().item()
                winner_label = label_map.get(winner_idx, "neutral")
                winner_prob = probs[i][winner_idx].item()
                
                # We only want to save positive or negative
                if winner_label in ["positive", "negative"] and winner_prob > 0.5:
                    # Is the aspect actually mentioned in the text?
                    # HF ABSA sometimes predicts strongly even if the aspect is implicitly mentioned.
                    # We will enforce explicit mention to avoid hallucination, or we can rely on sentence extraction.
                    evidence = extract_sentence(text_val, aspect)
                    if not evidence:
                        continue # If the word isn't explicitly there, we drop it to maintain quality.
                        
                    sentiment_score = prob_pos - prob_neg
                    
                    batch_params.append({
                        "game_id": r.game_id,
                        "aspect": aspect,
                        "sentiment": winner_label,
                        "sentiment_score": sentiment_score,
                        "confidence": winner_prob,
                        "evidence": evidence,
                        "model_used": "deberta-v3-large-absa",
                        "prompt_version": "hf_zero_shot",
                        "extracted_at": datetime.utcnow()
                    })
                    
            if batch_params:
                db.execute(text("""
                    INSERT INTO review_aspects (game_id, aspect, sentiment, sentiment_score, confidence, evidence, model_used, prompt_version, extracted_at)
                    VALUES (:game_id, :aspect, :sentiment, :sentiment_score, :confidence, :evidence, :model_used, :prompt_version, :extracted_at)
                """), batch_params)
                db.commit()
                total_aspects_found += len(batch_params)
                
    elapsed = time.time() - start_time
    time_per_review = elapsed / len(eligible_reviews)
    
    print("\n--- Extraction Complete ---")
    print(f"Processed {len(eligible_reviews)} reviews in {elapsed:.2f} seconds.")
    print(f"Average time per review: {time_per_review:.3f} seconds/review.")
    print(f"Total aspects extracted: {total_aspects_found}")
    print(f"Estimated time for 1M eligible reviews: {(time_per_review * 1000000)/3600:.2f} hours on a single {device} device.")

if __name__ == "__main__":
    main()
