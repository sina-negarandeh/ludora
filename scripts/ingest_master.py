import os
import time
import psycopg
import pandas as pd
from sqlalchemy import create_engine, text

from app.core.config import settings

def copy_csv_to_postgres(conn, table_name, csv_path):
    print(f"[{time.strftime('%X')}] COPYing {csv_path} into {table_name}...")
    with open(csv_path, 'r') as f:
        # Read the first line to get columns
        header = f.readline().strip()
        columns = header.split(',')
        # Reset file pointer
        f.seek(0)
        with conn.cursor() as cur:
            # We use copy expert so we can stream the file natively into Postgres.
            with cur.copy(f"COPY {table_name} ({', '.join(columns)}) FROM STDIN WITH (FORMAT CSV, HEADER)") as copy:
                while data := f.read(8192):
                    copy.write(data)
    print(f"[{time.strftime('%X')}] Done copying into {table_name}.")

def main():
    print(f"Connecting to database: {settings.DATABASE_URL}")
    engine = create_engine(settings.DATABASE_URL)
    
    # We use psycopg natively for COPY, but SQLAlchemy for the games dataframe
    db_url = settings.DATABASE_URL.replace('postgresql+psycopg://', 'postgresql://')
    
    # 1. Truncate everything
    with engine.connect() as conn:
        print("Truncating all tables...")
        conn.execute(text("TRUNCATE TABLE games, categories, mechanics, themes, subdomains, families, subfamilies, designers, publishers, artists, users, ratings, reviews, game_categories, game_mechanics, game_themes, game_subdomains, game_subfamilies, game_designers, game_publishers, game_artists, game_relations CASCADE"))
        conn.commit()

    # Run from the repo root, matching every other pipeline script. Override
    # via env var for Docker or any other cwd — see docs/setup/README.md.
    base_path = os.environ.get('PROCESSED_DATA_DIR', 'data/processed')
    
    # 2. Insert Games via Pandas (since CSV has extra columns we need to drop/rename)
    print(f"[{time.strftime('%X')}] Loading Games into Pandas...")
    df_games = pd.read_csv(os.path.join(base_path, 'master_games.csv'))
    
    # Map CSV columns to DB columns
    rename_map = {
        'image_url': 'image_path',
        'rank_boardgame': 'rank',
    }
    df_games.rename(columns=rename_map, inplace=True)
    
    db_cols = [
        'bgg_id', 'name', 'description', 'year_published', 'game_weight', 'avg_rating', 'median_rating',
        'min_players', 'max_players', 'mfg_playtime', 'min_age', 'image_path', 'rank', 'num_ratings',
        'num_comments', 'owned_count', 'trading_count', 'wanting_count', 'wishing_count',
        'min_playtime', 'max_playtime', 'bayes_avg_rating', 'stddev_rating', 'num_weight_votes',
        'thumbnail_url', 'kickstarted', 'is_reimplementation',
        'suggested_num_players', 'suggested_playerage', 'suggested_language_dependence',
    ]
    df_games_db = df_games[db_cols].copy()

    int_cols = [
        'year_published', 'min_players', 'max_players', 'mfg_playtime', 'min_age', 'rank', 'num_ratings',
        'num_comments', 'owned_count', 'trading_count', 'wanting_count', 'wishing_count',
        'min_playtime', 'max_playtime', 'num_weight_votes', 'kickstarted', 'is_reimplementation',
    ]
    for c in int_cols:
        df_games_db[c] = pd.to_numeric(df_games_db[c], errors='coerce').astype('Int64')
    
    clean_csv_path = os.path.join(base_path, 'master_games_clean.csv')
    print(f"[{time.strftime('%X')}] Writing clean games CSV...")
    df_games_db.to_csv(clean_csv_path, index=False)
    
    with psycopg.connect(db_url) as conn:
        copy_csv_to_postgres(conn, 'games', clean_csv_path)
        conn.commit()
    print(f"[{time.strftime('%X')}] Done inserting Games.")

    def copy_mapping_dedup(conn, table_name, csv_path):
        print(f"[{time.strftime('%X')}] Deduplicating {csv_path}...")
        df = pd.read_csv(csv_path)
        df.drop_duplicates(inplace=True)
        clean_path = csv_path.replace('.csv', '_clean.csv')
        df.to_csv(clean_path, index=False)
        copy_csv_to_postgres(conn, table_name, clean_path)

    # 3. Use COPY for everything else (Blazing Fast)
    with psycopg.connect(db_url) as conn:
        
        # Entities
        copy_csv_to_postgres(conn, 'subdomains', os.path.join(base_path, 'master_subdomains.csv'))
        copy_csv_to_postgres(conn, 'categories', os.path.join(base_path, 'master_categories.csv'))
        copy_csv_to_postgres(conn, 'themes', os.path.join(base_path, 'master_themes.csv'))
        copy_csv_to_postgres(conn, 'families', os.path.join(base_path, 'master_families.csv'))
        copy_csv_to_postgres(conn, 'subfamilies', os.path.join(base_path, 'master_subfamilies.csv'))
        copy_csv_to_postgres(conn, 'mechanics', os.path.join(base_path, 'master_mechanics.csv'))
        copy_csv_to_postgres(conn, 'designers', os.path.join(base_path, 'master_designers.csv'))
        copy_csv_to_postgres(conn, 'publishers', os.path.join(base_path, 'master_publishers.csv'))
        copy_csv_to_postgres(conn, 'artists', os.path.join(base_path, 'master_artists.csv'))
        conn.commit()

        # Mappings (often have duplicates from JSON source)
        copy_mapping_dedup(conn, 'game_subdomains', os.path.join(base_path, 'master_game_subdomains.csv'))
        copy_mapping_dedup(conn, 'game_categories', os.path.join(base_path, 'master_game_categories.csv'))
        copy_mapping_dedup(conn, 'game_themes', os.path.join(base_path, 'master_game_themes.csv'))
        copy_mapping_dedup(conn, 'game_subfamilies', os.path.join(base_path, 'master_game_subfamilies.csv'))
        copy_mapping_dedup(conn, 'game_mechanics', os.path.join(base_path, 'master_game_mechanics.csv'))
        copy_mapping_dedup(conn, 'game_designers', os.path.join(base_path, 'master_game_designers.csv'))
        copy_mapping_dedup(conn, 'game_publishers', os.path.join(base_path, 'master_game_publishers.csv'))
        copy_mapping_dedup(conn, 'game_artists', os.path.join(base_path, 'master_game_artists.csv'))
        conn.commit()

        # Users and Interactions
        copy_csv_to_postgres(conn, 'users', os.path.join(base_path, 'master_users.csv'))
        conn.commit()
        
        # Filter ratings and reviews to only include valid game_ids
        valid_game_ids = set(df_games_db['bgg_id'])

        def filter_csv_by_game(input_csv, game_col_idx):
            output_csv = input_csv.replace('.csv', '_clean.csv')
            print(f"[{time.strftime('%X')}] Filtering {input_csv} to keep only valid game IDs...")
            import csv
            with open(input_csv, 'r') as infile, open(output_csv, 'w', newline='') as outfile:
                reader = csv.reader(infile)
                writer = csv.writer(outfile)
                headers = next(reader)
                writer.writerow(headers)
                
                kept = 0
                for row in reader:
                    if int(row[game_col_idx]) in valid_game_ids:
                        writer.writerow(row)
                        kept += 1
            print(f"[{time.strftime('%X')}] Kept {kept} rows in {output_csv}.")
            return output_csv
            
        ratings_clean = filter_csv_by_game(os.path.join(base_path, 'master_ratings.csv'), 1)
        copy_csv_to_postgres(conn, 'ratings', ratings_clean)
        conn.commit()
        
        reviews_clean = filter_csv_by_game(os.path.join(base_path, 'master_reviews.csv'), 1)
        copy_csv_to_postgres(conn, 'reviews', reviews_clean)
        conn.commit()

        # Game relations (expansions/implementations/integrations) — game_id
        # is index 0; related_game_id may be legitimately empty (unresolved
        # name match) and is left as-is, not filtered.
        relations_clean = filter_csv_by_game(os.path.join(base_path, 'master_game_relations.csv'), 0)
        copy_csv_to_postgres(conn, 'game_relations', relations_clean)
        conn.commit()

    print(f"[{time.strftime('%X')}] Master Dataset Ingestion Complete!")

if __name__ == "__main__":
    main()
