import os
import sys
import time
import json
import argparse
from pathlib import Path
from collections import defaultdict

sys.path.append(str(Path(__file__).parent.parent.resolve()))
from sqlalchemy import create_engine, text
from app.database.session import SessionLocal
from scripts.absa_extract_hf import compute_quality_score, download_fasttext_model
import fasttext

def calculate_allocations(target, pos_count, mix_count, neg_count):
    total = pos_count + mix_count + neg_count
    if total == 0:
        return 0, 0, 0
        
    # Initial proportional allocation
    pos_alloc = int(target * (pos_count / total))
    mix_alloc = int(target * (mix_count / total))
    neg_alloc = int(target * (neg_count / total))
    
    # Give remaining slots to largest fractions
    current_total = pos_alloc + mix_alloc + neg_alloc
    remainder = target - current_total
    
    fractions = [
        ('pos', target * (pos_count / total) - pos_alloc),
        ('mix', target * (mix_count / total) - mix_alloc),
        ('neg', target * (neg_count / total) - neg_alloc)
    ]
    fractions.sort(key=lambda x: x[1], reverse=True)
    
    allocs = {'pos': pos_alloc, 'mix': mix_alloc, 'neg': neg_alloc}
    for i in range(remainder):
        allocs[fractions[i][0]] += 1
        
    # Check if any allocation exceeds availability
    avail = {'pos': pos_count, 'mix': mix_count, 'neg': neg_count}
    shortfall = 0
    for k in ['pos', 'mix', 'neg']:
        if allocs[k] > avail[k]:
            shortfall += allocs[k] - avail[k]
            allocs[k] = avail[k]
            
    # Redistribute shortfall
    while shortfall > 0:
        redistributed = False
        for k in ['pos', 'mix', 'neg']:
            if shortfall > 0 and allocs[k] < avail[k]:
                allocs[k] += 1
                shortfall -= 1
                redistributed = True
        if not redistributed:
            break
            
    return allocs['pos'], allocs['mix'], allocs['neg']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--top_n', type=int, default=100, help='Number of top ranked games to sample')
    parser.add_argument('--target_per_game', type=int, default=100, help='Max reviews to sample per game')
    args = parser.parse_args()

    base_dir = os.path.dirname(__file__)
    ft_model_path = os.path.join(base_dir, '../../data/models/lid.176.ftz')
    os.makedirs(os.path.dirname(ft_model_path), exist_ok=True)
    download_fasttext_model(ft_model_path)
    
    print("Loading fastText model...")
    ft_model = fasttext.load_model(ft_model_path)
    
    db = SessionLocal()
    engine = db.get_bind()
    
    print(f"Fetching reviews for top {args.top_n} games...")
    start_time = time.time()
    
    # Store sampled review IDs
    sampled_cache = {}
    total_sampled = 0
    
    with engine.connect() as conn:
        games_result = conn.execute(text(f"SELECT bgg_id FROM games WHERE rank <= {args.top_n} AND rank > 0 ORDER BY rank ASC"))
        game_ids = [row[0] for row in games_result]
        
        for g_idx, game_id in enumerate(game_ids):
            # Fetch all reviews for this game
            reviews_result = conn.execute(text("SELECT id, user_id, rating, comment FROM reviews WHERE game_id = :g_id AND comment IS NOT NULL"), {"g_id": game_id})
            
            user_best_review = {}
            for row in reviews_result:
                r_id = row[0]
                user_id = row[1]
                rating = row[2]
                comment = row[3]
                
                q_score = compute_quality_score(comment, ft_model)
                if q_score >= 0.6:
                    # 1. User uniqueness & Quality
                    # Note: We fallback to r_id for uniqueness if user_id is null (some datasets might lack user_id)
                    u_key = user_id if user_id is not None else r_id
                    if u_key not in user_best_review or q_score > user_best_review[u_key]['q_score']:
                        user_best_review[u_key] = {
                            'id': r_id,
                            'rating': rating,
                            'q_score': q_score
                        }
                        
            # Group into sentiment buckets
            buckets = {'pos': [], 'mix': [], 'neg': []}
            for u_key, r_data in user_best_review.items():
                rating = r_data['rating']
                if rating is None or rating < 4.0:
                    b = 'neg'
                elif rating >= 7.0:
                    b = 'pos'
                else:
                    b = 'mix'
                buckets[b].append(r_data)
                
            # Sort buckets by quality descending
            for b in buckets:
                buckets[b].sort(key=lambda x: x['q_score'], reverse=True)
                
            # Determine allocations
            pos_alloc, mix_alloc, neg_alloc = calculate_allocations(
                args.target_per_game, 
                len(buckets['pos']), 
                len(buckets['mix']), 
                len(buckets['neg'])
            )
            
            # Select reviews
            selected_ids = []
            selected_ids.extend([r['id'] for r in buckets['pos'][:pos_alloc]])
            selected_ids.extend([r['id'] for r in buckets['mix'][:mix_alloc]])
            selected_ids.extend([r['id'] for r in buckets['neg'][:neg_alloc]])
            
            if selected_ids:
                sampled_cache[str(game_id)] = selected_ids
                total_sampled += len(selected_ids)
                
            if (g_idx + 1) % 10 == 0:
                print(f"Processed {g_idx + 1}/{len(game_ids)} games. Total sampled so far: {total_sampled}")
                
    cache_path = os.path.join(base_dir, '../../data/stratified_samples.json')
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, 'w') as f:
        json.dump(sampled_cache, f)
        
    print(f"\\n--- Sampling Complete in {time.time()-start_time:.2f} seconds ---")
    print(f"Total games processed: {len(game_ids)}")
    print(f"Total reviews selected for ABSA: {total_sampled}")
    print(f"Saved cache to: {os.path.abspath(cache_path)}")

if __name__ == "__main__":
    main()
