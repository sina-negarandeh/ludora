import pandas as pd
import math
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add backend to path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.database.models import Game
from app.database.session import Base
from app.core.config import settings

def main():
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    
    print("Reading games.csv...")
    csv_path = os.path.join(os.path.dirname(__file__), '../data/raw/games.csv')
    if not os.path.exists(csv_path):
        csv_path = '/data/raw/games.csv'
    df = pd.read_csv(csv_path)
    
    print(f"Loaded {len(df)} games from CSV.")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("Truncating games table to repopulate...")
    session.execute(text("TRUNCATE TABLE games RESTART IDENTITY CASCADE"))
    session.commit()
    
    print("Inserting games into database...")
    batch_size = 1000
    games_to_insert = []
    
    # helper to handle nans
    def clean_val(val, default):
        if pd.isna(val) or math.isnan(val):
            return default
        return val

    for _, row in df.iterrows():
        cats = []
        for cat_name in ['Thematic', 'Strategy', 'War', 'Family', 'CGS', 'Abstract', 'Party', 'Childrens']:
            if row.get(f'Cat:{cat_name}') == 1:
                cats.append(cat_name)
                
        game = Game(
            bgg_id=int(row['BGGId']),
            name=str(row['Name']),
            description=str(row['Description']) if not pd.isna(row['Description']) else "",
            year_published=int(clean_val(row['YearPublished'], 0)),
            game_weight=float(clean_val(row['GameWeight'], 0.0)),
            avg_rating=float(clean_val(row['AvgRating'], 0.0)),
            min_players=int(clean_val(row['MinPlayers'], 0)),
            max_players=int(clean_val(row['MaxPlayers'], 0)),
            mfg_playtime=int(clean_val(row['MfgPlaytime'], 0)),
            min_age=int(clean_val(row['MfgAgeRec'], 0)),
            image_path=str(row['ImagePath']) if not pd.isna(row['ImagePath']) else "",
            rank=int(clean_val(row['Rank:boardgame'], 0)) if not pd.isna(row['Rank:boardgame']) and str(row['Rank:boardgame']).lower() != 'na' else None,
            categories=",".join(cats) if cats else None
        )
        games_to_insert.append(game)
        
        if len(games_to_insert) >= batch_size:
            session.bulk_save_objects(games_to_insert)
            session.commit()
            games_to_insert = []
            
    if games_to_insert:
        session.bulk_save_objects(games_to_insert)
        session.commit()
        
    print("Ingestion complete!")
    session.close()

if __name__ == "__main__":
    main()
