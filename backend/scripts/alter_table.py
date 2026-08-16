import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from sqlalchemy import text
from app.database.session import engine

def run():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE reviews ADD COLUMN language VARCHAR(10);"))
            print("Added language column.")
        except Exception as e:
            print(f"Column might already exist: {e}")
        
        try:
            conn.execute(text("CREATE INDEX ix_reviews_language ON reviews (language);"))
            print("Added index on language.")
        except Exception as e:
            print(f"Index might already exist: {e}")

if __name__ == "__main__":
    run()
