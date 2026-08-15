import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.database.models import Game
from app.core.config import settings

def get_bucket(val_str):
    val = float(val_str)
    return max(1.0, round(val * 2) / 2)

def main():
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    csv_path = os.path.join(os.path.dirname(__file__), '../data/raw/ratings_distribution.csv')
    print(f"Loading ratings distribution from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    
    score_cols = [c for c in df.columns if c not in ('BGGId', 'total_ratings')]
    
    # Initialize buckets with zeros (1.0, 1.5, ... 10.0)
    bucket_keys = [x / 2.0 for x in range(2, 21)]
    bucket_df = pd.DataFrame(0.0, index=df.index, columns=bucket_keys)
    
    # Sum columns into buckets
    for c in score_cols:
        bucket = get_bucket(c)
        bucket_df[bucket] += df[c]
    
    # Combine with BGGId and total_ratings
    df_result = pd.concat([df[['BGGId', 'total_ratings']], bucket_df], axis=1)
    
    print("Updating database...")
    updates = []
    
    # Ensure all buckets exist in df_result
    for k in bucket_keys:
        if k not in df_result.columns:
            df_result[k] = 0.0
            
    for _, row in df_result.iterrows():
        bgg_id = int(row['BGGId'])
        total_ratings = int(row['total_ratings']) if not pd.isna(row['total_ratings']) else 0
        
        import json
        
        # Build the 19-bucket distribution list
        dist = [int(row[k]) for k in bucket_keys]
        
        updates.append({
            'b_id': bgg_id,
            'n_ratings': total_ratings,
            'r_dist': json.dumps(dist)
        })
        
    if updates:
        # Batch update using raw SQL for performance
        stmt = text("""
            UPDATE games 
            SET num_ratings = :n_ratings, rating_distribution = CAST(:r_dist AS json)
            WHERE bgg_id = :b_id
        """)
        session.execute(stmt, updates)
        session.commit()
        
    print(f"Successfully updated rating distributions for {len(updates)} games.")

if __name__ == "__main__":
    main()
