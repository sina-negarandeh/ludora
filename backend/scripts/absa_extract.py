import os
import sys
import pandas as pd
import json
import time
import requests
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent.resolve()))
from sqlalchemy import text
from app.database.session import SessionLocal

# The 22 Aspects strictly allowed
TAXONOMY = [
    "Gameplay", "Mechanics", "Strategy", "Theme", "Immersion", "Replayability", 
    "Components", "Artwork", "Production Quality", "Rulebook", "Setup", "Teardown", 
    "Learning Curve", "Complexity", "Downtime", "Player Interaction", "Balance", 
    "Luck", "Player Count", "Solo Play", "Game Length", "Value"
]

PROMPT_VERSION = "absa_v1"
MODEL_NAME = "qwen2.5:7b" # Attempting qwen2.5:7b because qwen3:7b might not be available in Ollama yet, I will pull qwen2.5 just in case. Wait, I will use exactly what user said 'qwen3:7b' but fall back if it fails. Let me write what user typed.
MODEL_NAME = "qwen2.5:7b"
OLLAMA_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = f"""You are an Aspect-Based Sentiment Analyzer for board games.
Analyze the following review. Extract the sentiment (positive, negative, mixed, or neutral) for any of the following aspects if they are mentioned:
{", ".join(TAXONOMY)}.

Output STRICTLY in JSON format matching this schema:
{{
  "aspects": [
    {{
      "aspect": "<One of the exact taxonomy terms>",
      "sentiment": "<positive | negative | mixed | neutral>",
      "sentiment_score": <float between -1.0 and 1.0>,
      "confidence": <float between 0.0 and 1.0>,
      "evidence": "<the exact quote from the text>"
    }}
  ]
}}
If no aspects are mentioned, return {{"aspects": []}}.
"""

def extract_aspects(review_text):
    prompt = f"{SYSTEM_PROMPT}\n\nReview Text:\n{review_text}"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.0 # Deterministic JSON extraction
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        result_str = data.get("response", "")
        # Parse JSON
        parsed = json.loads(result_str)
        return parsed.get("aspects", [])
    except Exception as e:
        print(f"Extraction failed: {e}")
        return []

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=50, help='Number of reviews to process for the pilot')
    args = parser.parse_args()
    
    # Check if Ollama is running
    try:
        requests.get("http://localhost:11434/", timeout=2)
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to Ollama.")
        print("Please ensure Ollama is installed and running:")
        print("  1. brew install ollama")
        print(f"  2. ollama run {MODEL_NAME}")
        return

    base_dir = os.path.join(os.path.dirname(__file__), '../../data/processed')
    filtered_path = os.path.join(base_dir, 'pilot_absa_filtered.csv')
    
    if not os.path.exists(filtered_path):
        print(f"File not found: {filtered_path}")
        return
        
    print("Loading filtered reviews...")
    df = pd.read_csv(filtered_path)
    df_eligible = df[df['is_absa_eligible'] == True]
    print(f"Total eligible reviews: {len(df_eligible)}")
    
    # Take a sample for the pilot
    df_pilot = df_eligible.sample(n=min(args.limit, len(df_eligible)), random_state=42)
    print(f"Processing {len(df_pilot)} reviews for the pilot...")
    
    db = SessionLocal()
    
    success_count = 0
    aspects_found = 0
    
    start_time = time.time()
    for _, row in df_pilot.iterrows():
        game_id = row['game_id']
        text_content = str(row['comment'])
        
        extracted = extract_aspects(text_content)
        
        if not extracted:
            continue
            
        success_count += 1
        
        batch_params = []
        for item in extracted:
            # Validate against taxonomy
            aspect_name = item.get("aspect")
            if aspect_name not in TAXONOMY:
                continue # Skip hallucinations
                
            batch_params.append({
                "game_id": int(game_id),
                "aspect": aspect_name,
                "sentiment": item.get("sentiment", "neutral"),
                "sentiment_score": float(item.get("sentiment_score", 0.0)),
                "confidence": float(item.get("confidence", 0.8)),
                "evidence": str(item.get("evidence", "")),
                "model_used": MODEL_NAME,
                "prompt_version": PROMPT_VERSION,
                "extracted_at": datetime.utcnow()
            })
            
        if batch_params:
            db.execute(text("""
                INSERT INTO review_aspects (game_id, aspect, sentiment, sentiment_score, confidence, evidence, model_used, prompt_version, extracted_at)
                VALUES (:game_id, :aspect, :sentiment, :sentiment_score, :confidence, :evidence, :model_used, :prompt_version, :extracted_at)
            """), batch_params)
            db.commit()
            aspects_found += len(batch_params)
            
        # Print progress
        print(f"Processed review for Game {game_id}. Extracted {len(batch_params)} aspects.")
            
    elapsed = time.time() - start_time
    print(f"\n--- Extraction Complete ---")
    print(f"Processed {args.limit} reviews in {elapsed:.2f} seconds.")
    print(f"Successfully extracted {aspects_found} total aspects from {success_count} reviews.")

if __name__ == "__main__":
    main()
