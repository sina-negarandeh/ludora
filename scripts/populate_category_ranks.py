import sys
import os
import pandas as pd
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.database.models import Game
from app.core.config import settings

def clean_rank(val):
    try:
        val = int(val)
        # BGG uses 21926 as a placeholder for unranked categories in this dataset
        return val if 0 < val < 21926 else None
    except:
        return None

def main():
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    csv_path = os.path.join(os.path.dirname(__file__), '../data/raw/games.csv')
    print(f"Loading games data from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    
    rank_mapping = {
        'Rank:strategygames': 'Strategy Games',
        'Rank:abstracts': 'Abstract Games',
        'Rank:familygames': 'Family Games',
        'Rank:thematic': 'Thematic Games',
        'Rank:cgs': 'Customizable Games',
        'Rank:wargames': 'Wargames',
        'Rank:partygames': 'Party Games',
        'Rank:childrensgames': "Children's Games"
    }
    
    print("Parsing ranks and updating database...")
    updates = []
    
    for _, row in df.iterrows():
        bgg_id = int(row['BGGId'])
        
        category_ranks = {}
        for col, display_name in rank_mapping.items():
            if col in row and not pd.isna(row[col]):
                rank = clean_rank(row[col])
                if rank is not None:
                    category_ranks[display_name] = rank
                    
        # Only update if we have data or if we want to set it to empty json {}
        # Actually it's cleaner to store null if empty
        r_json = json.dumps(category_ranks) if category_ranks else None
            
        updates.append({
            'b_id': bgg_id,
            'c_ranks': r_json
        })
        
    if updates:
        # Batch update using raw SQL for performance
        stmt = text("""
            UPDATE games 
            SET category_ranks = CAST(:c_ranks AS json)
            WHERE bgg_id = :b_id
        """)
        
        # Execute in chunks to avoid overwhelming memory
        chunk_size = 5000
        for i in range(0, len(updates), chunk_size):
            session.execute(stmt, updates[i:i + chunk_size])
        
        session.commit()
        
    print(f"Successfully updated category ranks for {len(updates)} games.")

if __name__ == "__main__":
    main()
