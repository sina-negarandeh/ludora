import os
import sys
import time
import psycopg
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.core.config import settings

def copy_csv_to_postgres(conn, table_name, csv_path):
    print(f"[{time.strftime('%X')}] COPYing {csv_path} into {table_name}...")
    with open(csv_path, 'r') as f:
        header = f.readline().strip()
        columns = header.split(',')
        f.seek(0)
        with conn.cursor() as cur:
            with cur.copy(f"COPY {table_name} ({', '.join(columns)}) FROM STDIN WITH (FORMAT CSV, HEADER)") as copy:
                while data := f.read(8192):
                    copy.write(data)
    print(f"[{time.strftime('%X')}] Done copying into {table_name}.")

def main():
    print(f"Connecting to database...")
    db_url = settings.DATABASE_URL.replace('postgresql+psycopg://', 'postgresql://')
    base_path = '../data/processed'

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            print("Truncating themes...")
            cur.execute("TRUNCATE TABLE themes CASCADE")
            
        conn.commit()

        # Themes
        copy_csv_to_postgres(conn, 'themes', os.path.join(base_path, 'master_themes.csv'))
        conn.commit()

        # Game Themes Mapping
        csv_path = os.path.join(base_path, 'master_game_themes.csv')
        df = pd.read_csv(csv_path)
        df.drop_duplicates(inplace=True)
        clean_path = csv_path.replace('.csv', '_clean.csv')
        df.to_csv(clean_path, index=False)
        
        copy_csv_to_postgres(conn, 'game_themes', clean_path)
        conn.commit()

    print("Successfully ingested themes!")

if __name__ == "__main__":
    main()
