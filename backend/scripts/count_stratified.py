import os
import sys
import time
import hashlib
from pathlib import Path
from collections import defaultdict

sys.path.append(str(Path(__file__).parent.parent.resolve()))
from sqlalchemy import create_engine, text
from app.database.session import SessionLocal
from scripts.absa_extract_hf import compute_quality_score
import fasttext

def main():
    base_dir = os.path.dirname(__file__)
    ft_model_path = os.path.join(base_dir, '../../data/models/lid.176.ftz')
    print("Loading fastText model...")
    ft_model = fasttext.load_model(ft_model_path)
    
    print("Connecting to database...")
    db = SessionLocal()
    engine = db.get_bind()
    
    seen_hashes = set()
    game_buckets = defaultdict(lambda: {'pos': 0, 'mix': 0, 'neg': 0})
    
    total_scanned = 0
    total_eligible = 0
    total_exact_dupes = 0
    
    start_time = time.time()
    
    # We use raw connection for speed on 4.2M rows
    with engine.connect() as conn:
        print("Executing query to fetch all reviews...")
        # yield_per is not supported directly in raw connection easily without server-side cursors in Postgres,
        # but for SQLite, fetchmany() works well.
        result = conn.execute(text("SELECT game_id, rating, comment FROM reviews WHERE comment IS NOT NULL"))
        
        while True:
            chunk = result.fetchmany(50000)
            if not chunk:
                break
                
            for row in chunk:
                game_id = row[0]
                rating = row[1]
                comment = row[2]
                
                total_scanned += 1
                if total_scanned % 500000 == 0:
                    print(f"Scanned {total_scanned} rows...")
                    
                txt = comment.lower().strip()
                h = hashlib.md5(txt.encode('utf-8')).hexdigest()
                
                if h in seen_hashes:
                    total_exact_dupes += 1
                    continue
                seen_hashes.add(h)
                
                # We skip length requirement in quality score just to be fast?
                # compute_quality_score already handles length.
                q_score = compute_quality_score(comment, ft_model)
                if q_score >= 0.6:
                    total_eligible += 1
                    # Bucket
                    if rating is None:
                        bucket = 'mix' # Fallback
                    elif rating >= 7.0:
                        bucket = 'pos'
                    elif rating >= 4.0:
                        bucket = 'mix'
                    else:
                        bucket = 'neg'
                        
                    game_buckets[game_id][bucket] += 1

    print(f"\n--- Scanning Complete in {time.time()-start_time:.2f} seconds ---")
    print(f"Total rows scanned: {total_scanned}")
    print(f"Total exact duplicates dropped: {total_exact_dupes}")
    print(f"Total eligible globally (Quality >= 0.6): {total_eligible}")
    
    # Calculate stratified sample sizes
    total_stratified_sampled = 0
    target_per_game = 50
    
    for g_id, buckets in game_buckets.items():
        pos = buckets['pos']
        mix = buckets['mix']
        neg = buckets['neg']
        
        available = [pos, mix, neg]
        available.sort()
        
        sampled = 0
        remaining_target = target_per_game
        for i, avail in enumerate(available):
            buckets_left = 3 - i
            fair_share = remaining_target // buckets_left
            take = min(avail, fair_share)
            sampled += take
            remaining_target -= take
            
        total_stratified_sampled += sampled
        
    print(f"\n--- Stratified Sampling Results ---")
    print(f"Target max reviews per game: {target_per_game}")
    print(f"Total games with eligible reviews: {len(game_buckets)}")
    print(f"FINAL NUMBER OF REVIEWS TO PROCESS globally: {total_stratified_sampled}")
    
    # Calculate estimated compute time
    time_per_review = 0.388 # seconds
    total_seconds = total_stratified_sampled * time_per_review
    hours = total_seconds / 3600
    days = hours / 24
    print(f"\nEstimated compute time at 0.388s/review: {hours:.1f} hours ({days:.1f} days)")

if __name__ == "__main__":
    main()
