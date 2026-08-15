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
    if val <= 1.0: return 1
    elif val <= 2.0: return 2
    elif val <= 3.0: return 3
    elif val <= 4.0: return 4
    elif val <= 5.0: return 5
    elif val <= 6.0: return 6
    elif val <= 7.0: return 7
    elif val <= 8.0: return 8
    elif val <= 9.0: return 9
    else: return 10

def main():
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    csv_path = os.path.join(os.path.dirname(__file__), '../data/raw/ratings_distribution.csv')
    print(f"Loading ratings distribution from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    
    score_cols = [c for c in df.columns if c not in ('BGGId', 'total_ratings')]
    
    # Initialize buckets with zeros
    bucket_df = pd.DataFrame(0.0, index=df.index, columns=range(1, 11))
    
    # Sum columns into buckets
    for c in score_cols:
        bucket = get_bucket(c)
        bucket_df[bucket] += df[c]
    
    # Combine with BGGId and total_ratings
    df_result = pd.concat([df[['BGGId', 'total_ratings']], bucket_df], axis=1)
    
    print("Updating database...")
    updates = []
    
    # Ensure all buckets 1-10 exist in df_result
    for i in range(1, 11):
        if i not in df_result.columns:
            df_result[i] = 0.0
            
    for _, row in df_result.iterrows():
        bgg_id = int(row['BGGId'])
        total_ratings = int(row['total_ratings']) if not pd.isna(row['total_ratings']) else 0
        
        import json
        
        # Build the 10-bucket distribution list
        dist = [int(row[i]) for i in range(1, 11)]
        
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
