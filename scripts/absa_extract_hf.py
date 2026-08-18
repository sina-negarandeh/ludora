import os
import time
import argparse
import re
from datetime import datetime
import requests
import mlflow

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import fasttext

from sqlalchemy import text
from app.database.session import SessionLocal
from app.database.models import Review
from app.core.ml_config import ABSAConfig
from app.core.mlflow_utils import tracked_run

# The 22 Aspects strictly allowed
TAXONOMY = ABSAConfig.TAXONOMY

def download_fasttext_model(model_path):
    if not os.path.exists(model_path):
        print("Downloading fastText language model...")
        r = requests.get(ABSAConfig.FASTTEXT_MODEL_URL, allow_redirects=True)
        r.raise_for_status()
        tmp_path = model_path + ".tmp"
        with open(tmp_path, 'wb') as f:
            f.write(r.content)
        os.replace(tmp_path, model_path)
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

    length_score = min(len(words) / ABSAConfig.QUALITY_LENGTH_NORM_WORDS, 1.0)

    spam_penalty = 0.0
    if re.search(ABSAConfig.QUALITY_SPAM_PATTERN, text_val):
        spam_penalty = ABSAConfig.QUALITY_SPAM_PENALTY

    text_lower = set(word.lower() for word in words)
    aspect_signal = min(
        len(text_lower.intersection(ABSAConfig.QUALITY_GAME_WORDS)) * ABSAConfig.QUALITY_ASPECT_SIGNAL_STEP,
        ABSAConfig.QUALITY_ASPECT_SIGNAL_CAP,
    )

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
    parser.add_argument('--limit', type=int, default=20, help='Number of eligible reviews to process per game')
    parser.add_argument('--game_id', type=int, default=None, help='BGG ID for the game to test. If omitted and --sampled is used, it will process all games in the cache.')
    parser.add_argument('--sampled', action='store_true', help='Use the stratified sample cache if available')
    args = parser.parse_args()
    
    base_dir = os.path.dirname(__file__)
    
    db = SessionLocal()
    
    games_to_process = []
    sampled_cache = {}
    
    if args.sampled:
        import json
        cache_path = os.path.join(base_dir, '../data/stratified_samples.json')
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                sampled_cache = json.load(f)
                
            if args.game_id:
                if str(args.game_id) in sampled_cache:
                    games_to_process = [args.game_id]
                else:
                    print(f"Game {args.game_id} not found in sample cache.")
                    return
            else:
                games_to_process = [int(k) for k in sampled_cache.keys()]
        else:
            print(f"Stratified sample cache not found at {cache_path}. Falling back to default behavior.")
            args.sampled = False
            if not args.game_id:
                games_to_process = [224517] # default Brass
            else:
                games_to_process = [args.game_id]
    else:
        if not args.game_id:
            games_to_process = [224517] # default Brass
        else:
            games_to_process = [args.game_id]
            
    if not args.sampled:
        ft_model_path = os.path.join(base_dir, '../data/models/lid.176.ftz')
        os.makedirs(os.path.dirname(ft_model_path), exist_ok=True)
        download_fasttext_model(ft_model_path)
        
        print("Loading fastText model for quality filtering...")
        global ft_model # needed if we refactor, but keeping it simple
        ft_model = fasttext.load_model(ft_model_path)

    # Load HF Model once
    device = torch.device("mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu"))
    print(f"Loading DeBERTa ABSA model on device: {device} ...")

    model_name = ABSAConfig.MODEL_NAME
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name).to(device)
    model.eval()

    label_map = {0: "negative", 1: "neutral", 2: "positive"}

    total_aspects_found = 0
    start_time = time.time()

    # Load processed games to avoid repeating work
    processed_games = [r[0] for r in db.execute(text("SELECT DISTINCT game_id FROM review_aspects")).fetchall()]

    for game_id in games_to_process:
        if game_id in processed_games:
            print(f"Skipping Game ID {game_id} (already processed)...")
            continue
            
        print(f"\nProcessing Game ID {game_id}...")
        eligible_reviews = []
        
        if args.sampled:
            sampled_ids = sampled_cache.get(str(game_id), [])
            if sampled_ids:
                print(f"Using {len(sampled_ids)} sampled reviews from cache for game {game_id}.")
                eligible_reviews = db.query(Review).filter(Review.id.in_(sampled_ids)).all()
        else:
            reviews = db.query(Review).filter(Review.game_id == game_id).yield_per(1000)
            for r in reviews:
                if r.comment:
                    q_score = compute_quality_score(r.comment, ft_model)
                    if q_score >= ABSAConfig.QUALITY_SCORE_THRESHOLD:
                        eligible_reviews.append(r)
                        if len(eligible_reviews) >= args.limit:
                            break
            print(f"Found {len(eligible_reviews)} highly eligible reviews out of limit {args.limit}.")
            
        if not eligible_reviews:
            print(f"No eligible reviews found for game {game_id}.")
            continue
            
        with torch.no_grad():
            for r in eligible_reviews:
                text_val = r.comment
                
                batch_params = []
                BATCH_SIZE = ABSAConfig.BATCH_SIZE

                # Process the 22 aspects in small chunks to avoid Out-Of-Memory (OOM) crashes
                for chunk_start in range(0, len(TAXONOMY), BATCH_SIZE):
                    aspect_chunk = TAXONOMY[chunk_start:chunk_start + BATCH_SIZE]
                    texts_chunk = [text_val] * len(aspect_chunk)
                    
                    inputs = tokenizer(texts_chunk, aspect_chunk, return_tensors="pt", padding=True, truncation=True, max_length=256).to(device)
                    outputs = model(**inputs)
                    probs_chunk = torch.softmax(outputs.logits, dim=1)
                    
                    for idx, aspect in enumerate(aspect_chunk):
                        prob_neg = probs_chunk[idx][0].item()
                        prob_pos = probs_chunk[idx][2].item()
                        
                        # Determine winner
                        winner_idx = probs_chunk[idx].argmax().item()
                        winner_label = label_map.get(winner_idx, "neutral")
                        winner_prob = probs_chunk[idx][winner_idx].item()
                        
                        # We only want to save positive or negative
                        if winner_label in ["positive", "negative"] and winner_prob > ABSAConfig.WINNER_PROB_THRESHOLD:
                            evidence = extract_sentence(text_val, aspect)
                            if not evidence:
                                continue 
                                
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
    total_reviews_processed = sum([len(sampled_cache.get(str(g), [])) if args.sampled else args.limit for g in games_to_process])
    if total_reviews_processed == 0: total_reviews_processed = 1
    time_per_review = elapsed / total_reviews_processed
    
    print("\n--- Extraction Complete ---")
    print(f"Processed {len(eligible_reviews)} reviews in {elapsed:.2f} seconds.")
    print(f"Average time per review: {time_per_review:.3f} seconds/review.")
    print(f"Total aspects extracted: {total_aspects_found}")
    print(f"Estimated time for 1M eligible reviews: {(time_per_review * 1000000)/3600:.2f} hours on a single {device} device.")

    mlflow.log_params({
        "model_name": ABSAConfig.MODEL_NAME,
        "taxonomy_size": len(TAXONOMY),
        "batch_size": ABSAConfig.BATCH_SIZE,
        "winner_prob_threshold": ABSAConfig.WINNER_PROB_THRESHOLD,
        "quality_score_threshold": ABSAConfig.QUALITY_SCORE_THRESHOLD,
        "sampled": args.sampled,
        "n_games": len(games_to_process),
    })
    mlflow.log_metrics({
        "total_aspects_extracted": total_aspects_found,
        "elapsed_seconds": elapsed,
    })

if __name__ == "__main__":
    with tracked_run("reviews/absa", run_name="extract"):
        main()
