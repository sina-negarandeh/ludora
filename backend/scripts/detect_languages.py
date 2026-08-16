import os
import sys
import time
import argparse
import requests
from pathlib import Path
import fasttext
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent.resolve()))
from sqlalchemy import text
from app.database.session import engine

def download_fasttext_model(model_path):
    if not os.path.exists(model_path):
        print("Downloading fastText language model...")
        url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
        r = requests.get(url, allow_redirects=True)
        with open(model_path, 'wb') as f:
            f.write(r.content)
        print("Downloaded.")

def detect_language(ft_model, text_str):
    if not isinstance(text_str, str) or not text_str.strip():
        return 'unknown'
    clean_text = text_str.replace('\n', ' ')
    langs, probs = ft_model.predict(clean_text, k=1)
    # langs[0] is typically '__label__en'
    lang_code = langs[0].replace('__label__', '')
    # If confidence is too low, we might just mark it unknown, but let's just use the best guess
    if probs[0] < 0.5:
        # Check if we should fallback, but fasttext is usually confident.
        pass
    return lang_code[:10] # ensure it fits in VARCHAR(10)

def run(limit=None):
    model_path = os.path.join(os.path.dirname(__file__), "lid.176.ftz")
    download_fasttext_model(model_path)
    print("Loading fasttext model...")
    ft_model = fasttext.load_model(model_path)
    
    batch_size = 10000
    total_processed = 0
    start_time = time.time()
    
    with engine.begin() as conn:
        print("Checking for rows to update...")
        # Get count
        if limit:
            count_res = conn.execute(text("SELECT COUNT(id) FROM reviews WHERE language IS NULL LIMIT :limit"), {"limit": limit})
            total_remaining = min(count_res.scalar(), limit)
        else:
            count_res = conn.execute(text("SELECT COUNT(id) FROM reviews WHERE language IS NULL"))
            total_remaining = count_res.scalar()
            
        print(f"Found {total_remaining} reviews without a language.")
        if total_remaining == 0:
            print("Done.")
            return

    while True:
        with engine.connect() as conn:
            # Fetch a batch
            query = "SELECT id, comment FROM reviews WHERE language IS NULL"
            if limit:
                fetch_limit = min(batch_size, limit - total_processed)
            else:
                fetch_limit = batch_size
                
            if fetch_limit <= 0:
                break
                
            query += f" LIMIT {fetch_limit}"
            
            result = conn.execute(text(query))
            rows = result.fetchall()
            
            if not rows:
                break
            
            # Process batch
            updates = []
            for row in rows:
                lang = detect_language(ft_model, row.comment)
                updates.append({"b_id": row.id, "b_lang": lang})
                
            # Bulk update
            if updates:
                conn.execute(
                    text("UPDATE reviews SET language = :b_lang WHERE id = :b_id"),
                    updates
                )
                conn.commit()
            
            total_processed += len(rows)
            elapsed = time.time() - start_time
            rate = total_processed / elapsed if elapsed > 0 else 0
            print(f"Processed {total_processed} rows (Rate: {rate:.2f} rows/sec)...")
            
            if limit and total_processed >= limit:
                break

    total_time = time.time() - start_time
    print(f"Complete. Processed {total_processed} rows in {total_time:.2f} seconds.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows to process")
    args = parser.parse_args()
    run(limit=args.limit)
