import pandas as pd
import math
from sqlalchemy import create_engine, text, insert
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add backend to path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.database.models import Game, Category, Mechanic, Designer, Publisher
from app.database.models import GameCategory, GameMechanic, GameDesigner, GamePublisher
from app.core.config import settings

def clean_val(val, default):
    if pd.isna(val) or math.isnan(val):
        return default
    return val

def extract_associations(df, name_map, id_key):
    assoc_list = []
    names = df.columns.drop('BGGId').tolist()
    for row in df.itertuples(index=False):
        bgg_id = int(row.BGGId)
        for i, val in enumerate(row[1:]):
            if val == 1:
                assoc_list.append({"game_id": bgg_id, id_key: name_map[names[i]]})
    return assoc_list

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def main():
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Truncating all tables...")
    session.execute(text("TRUNCATE TABLE games, categories, mechanics, designers, publishers CASCADE"))
    session.commit()

    base_path = '/data/raw' if os.path.exists('/data/raw/games.csv') else os.path.join(os.path.dirname(__file__), '../data/raw')
    
    print("Loading CSVs...")
    df_games = pd.read_csv(os.path.join(base_path, 'games.csv'))
    df_mechanics = pd.read_csv(os.path.join(base_path, 'mechanics.csv'))
    df_designers = pd.read_csv(os.path.join(base_path, 'designers_reduced.csv'))
    df_publishers = pd.read_csv(os.path.join(base_path, 'publishers_reduced.csv'))

    print("Populating Entities...")
    cat_names = ['Thematic', 'Strategy', 'War', 'Family', 'CGS', 'Abstract', 'Party', 'Childrens']
    mech_names = list(df_mechanics.columns.drop('BGGId'))
    des_names = list(df_designers.columns.drop('BGGId'))
    pub_names = list(df_publishers.columns.drop('BGGId'))

    categories = [Category(name=n) for n in cat_names]
    mechanics = [Mechanic(name=n) for n in mech_names]
    designers = [Designer(name=n) for n in des_names]
    publishers = [Publisher(name=n) for n in pub_names]
    
    session.add_all(categories + mechanics + designers + publishers)
    session.commit()

    cat_map = {c.name: c.id for c in session.query(Category).all()}
    mech_map = {m.name: m.id for m in session.query(Mechanic).all()}
    des_map = {d.name: d.id for d in session.query(Designer).all()}
    pub_map = {p.name: p.id for p in session.query(Publisher).all()}

    print(f"Inserting {len(df_games)} Games...")
    games_to_insert = []
    for _, row in df_games.iterrows():
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
            rank=int(clean_val(row['Rank:boardgame'], 0)) if not pd.isna(row['Rank:boardgame']) and str(row['Rank:boardgame']).lower() != 'na' else None
        )
        games_to_insert.append(game)
    session.bulk_save_objects(games_to_insert)
    session.commit()

    print("Building Categories association...")
    gc_list = []
    for _, row in df_games.iterrows():
        bgg_id = int(row['BGGId'])
        for cat in cat_names:
            if row.get(f'Cat:{cat}') == 1:
                gc_list.append({"game_id": bgg_id, "category_id": cat_map[cat]})
    
    print("Extracting Mechanics...")
    gm_list = extract_associations(df_mechanics, mech_map, "mechanic_id")
    
    print("Extracting Designers...")
    gd_list = extract_associations(df_designers, des_map, "designer_id")
    
    print("Extracting Publishers...")
    gp_list = extract_associations(df_publishers, pub_map, "publisher_id")

    print("Inserting Associations in batches...")
    batch_size = 50000
    if gc_list:
        for chunk in chunk_list(gc_list, batch_size):
            session.execute(insert(GameCategory), chunk)
    if gm_list:
        for chunk in chunk_list(gm_list, batch_size):
            session.execute(insert(GameMechanic), chunk)
    if gd_list:
        for chunk in chunk_list(gd_list, batch_size):
            session.execute(insert(GameDesigner), chunk)
    if gp_list:
        for chunk in chunk_list(gp_list, batch_size):
            session.execute(insert(GamePublisher), chunk)
            
    session.commit()
    print("Ingestion complete!")

if __name__ == "__main__":
    main()
