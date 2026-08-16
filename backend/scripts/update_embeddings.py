import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from sqlalchemy import text
from app.database.session import SessionLocal
from sentence_transformers import SentenceTransformer

def build_structured_document(game_name, description, themes, mechanics, categories):
    doc_parts = []
    
    if game_name:
        doc_parts.append(f"Name: {game_name}")
        
    if description:
        # truncate description slightly if it's monstrously long, but 384 model can handle 512 tokens
        doc_parts.append(f"Description:\n{description[:1500]}")
        
    if themes:
        doc_parts.append("Themes:\n" + "\n".join(themes))
        
    if mechanics:
        doc_parts.append("Mechanics:\n" + "\n".join(mechanics))
        
    if categories:
        doc_parts.append("Categories:\n" + "\n".join(categories))
        
    return "\n\n".join(doc_parts)

def update_embeddings():
    print("Loading embedding model (all-MiniLM-L6-v2)...")
    # Using a fast, standard model for semantic search
    model_name = "all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name)
    
    db = SessionLocal()
    
    # Query to fetch games and their relevant metadata
    # We omit designers, artists, and publishers as requested by the user
    query = """
        SELECT 
            g.bgg_id,
            g.name,
            g.description,
            (SELECT array_agg(t.name) FROM game_themes gt JOIN themes t ON gt.theme_id = t.id WHERE gt.game_id = g.bgg_id) as themes,
            (SELECT array_agg(m.name) FROM game_mechanics gm JOIN mechanics m ON gm.mechanic_id = m.id WHERE gm.game_id = g.bgg_id) as mechanics,
            (SELECT array_agg(c.name) FROM game_categories gc JOIN categories c ON gc.category_id = c.id WHERE gc.game_id = g.bgg_id) as categories
        FROM games g
    """
    
    print("Fetching games from database...")
    games = db.execute(text(query)).fetchall()
    print(f"Loaded {len(games)} games to process.")
    
    # We will process in batches to save memory and commit efficiently
    batch_size = 500
    total_processed = 0
    
    for i in range(0, len(games), batch_size):
        batch = games[i:i+batch_size]
        
        bgg_ids = []
        documents = []
        
        for row in batch:
            bgg_ids.append(row.bgg_id)
            doc = build_structured_document(
                row.name, 
                row.description, 
                row.themes or [], 
                row.mechanics or [], 
                row.categories or []
            )
            documents.append(doc)
            
        print(f"Encoding batch {i//batch_size + 1}/{(len(games) + batch_size - 1)//batch_size}...")
        embeddings = model.encode(documents, convert_to_numpy=True)
        
        # Prepare for bulk update
        update_query = text("""
            UPDATE games
            SET embedding = :emb,
                embedding_model = :model_name,
                embedding_updated_at = :updated_at
            WHERE bgg_id = :bgg_id
        """)
        
        # We need to execute the updates
        update_params = []
        now = datetime.utcnow()
        for idx, emb in enumerate(embeddings):
            # pgvector accepts lists for vectors
            update_params.append({
                "emb": emb.tolist(),
                "model_name": model_name,
                "updated_at": now,
                "bgg_id": bgg_ids[idx]
            })
            
        db.execute(update_query, update_params)
        db.commit()
        
        total_processed += len(batch)
        print(f"Saved {total_processed} / {len(games)} embeddings.")
        
    print("Embedding update complete!")

if __name__ == "__main__":
    update_embeddings()
