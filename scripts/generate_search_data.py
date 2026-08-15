import sys
import os
import datetime
from sqlalchemy import create_engine, func, update
from sqlalchemy.orm import sessionmaker

# Add backend to path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.database.models import Game
from app.core.config import settings
from sentence_transformers import SentenceTransformer

def main():
    print("Loading SentenceTransformer model 'all-MiniLM-L6-v2'...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    games = session.query(Game).all()
    total_games = len(games)
    print(f"Found {total_games} games to process.")

    batch_size = 100
    for i in range(0, total_games, batch_size):
        batch = games[i:i+batch_size]
        print(f"Processing batch {i // batch_size + 1}/{(total_games + batch_size - 1) // batch_size}...")
        
        for game in batch:
            cat_str = ", ".join([c.name for c in game.categories])
            mech_str = ", ".join([m.name for m in game.mechanics])
            des_str = ", ".join([d.name for d in game.designers])
            pub_str = ", ".join([p.name for p in game.publishers])
            art_str = ", ".join([a.name for a in game.artists])
            
            search_text = (
                f"Name: {game.name}\n"
                f"Description: {game.description or ''}\n"
                f"Categories: {cat_str}\n"
                f"Mechanics: {mech_str}\n"
                f"Designers: {des_str}\n"
                f"Publishers: {pub_str}\n"
                f"Artists: {art_str}"
            )
            
            # Generate embedding
            embedding = model.encode(search_text).tolist()
            
            # Update DB using explicit UPDATE to leverage func.to_tsvector
            stmt = update(Game).where(Game.bgg_id == game.bgg_id).values(
                embedding=embedding,
                embedding_model="all-MiniLM-L6-v2",
                embedding_updated_at=datetime.datetime.utcnow(),
                search_vector=func.to_tsvector('english', search_text)
            )
            session.execute(stmt)
            
        session.commit()
        
    print("Search data generation complete!")

if __name__ == "__main__":
    main()
