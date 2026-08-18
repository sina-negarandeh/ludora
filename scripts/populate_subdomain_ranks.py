import os
import pandas as pd
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

RAW_DATA_JVANELTEREN_DIR = os.environ.get(
    'RAW_DATA_JVANELTEREN_DIR',
    'data/raw/kaggle_datasets_jvanelteren_boardgamegeek-reviews',
)


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

    csv_path = os.path.join(RAW_DATA_JVANELTEREN_DIR, 'games_detailed_info2025.csv')
    print(f"Loading games data from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    df.rename(columns={'id': 'BGGId'}, inplace=True)
    
    rank_mapping = {
        'Strategy Game Rank': 'Strategy',
        'Abstract Game Rank': 'Abstract',
        'Family Game Rank': 'Family',
        'Thematic Rank': 'Thematic',
        'Customizable Rank': 'CGS',
        'War Game Rank': 'War',
        'Party Game Rank': 'Party',
        "Children's Game Rank": 'Childrens'
    }
    
    print("Parsing ranks and updating database...")
    updates = []
    
    for _, row in df.iterrows():
        bgg_id = int(row['BGGId'])
        
        subdomain_ranks = {}
        for col, display_name in rank_mapping.items():
            if col in row and not pd.isna(row[col]):
                rank = clean_rank(row[col])
                if rank is not None:
                    subdomain_ranks[display_name] = rank

        # Only update if we have data or if we want to set it to empty json {}
        # Actually it's cleaner to store null if empty
        r_json = json.dumps(subdomain_ranks) if subdomain_ranks else None
            
        updates.append({
            'b_id': bgg_id,
            'c_ranks': r_json
        })
        
    if updates:
        # Batch update using raw SQL for performance
        stmt = text("""
            UPDATE games
            SET subdomain_ranks = CAST(:c_ranks AS json)
            WHERE bgg_id = :b_id
        """)
        
        # Execute in chunks to avoid overwhelming memory
        chunk_size = 5000
        for i in range(0, len(updates), chunk_size):
            session.execute(stmt, updates[i:i + chunk_size])
        
        session.commit()
        
    print(f"Successfully updated subdomain ranks for {len(updates)} games.")

if __name__ == "__main__":
    main()
