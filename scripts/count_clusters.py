import os
import time
import torch

from app.database.session import SessionLocal
from app.database.models import Review
from absa_extract_hf import compute_quality_score
import fasttext
from sentence_transformers import SentenceTransformer, util

def main():
    base_dir = os.path.dirname(__file__)
    ft_model_path = os.path.join(base_dir, '../data/models/lid.176.ftz')
    ft_model = fasttext.load_model(ft_model_path)
    
    db = SessionLocal()
    game_id = 224517
    
    print(f"Fetching reviews for Brass: Birmingham (ID {game_id})...")
    reviews = db.query(Review).filter(Review.game_id == game_id).all()
    
    eligible_reviews = []
    
    for r in reviews:
        if r.comment:
            q_score = compute_quality_score(r.comment, ft_model)
            if q_score >= 0.6:
                eligible_reviews.append(r)
                
    print(f"Total eligible reviews before deduplication: {len(eligible_reviews)}")
    
    # 1. Exact text hash deduplication (already in our initial thought process, but let's re-verify)
    seen_exact = set()
    unique_exact = []
    for r in eligible_reviews:
        txt = r.comment.lower().strip()
        if txt not in seen_exact:
            seen_exact.add(txt)
            unique_exact.append(r)
            
    print(f"After exact lower-case match removal: {len(unique_exact)}")
    
    # 2. Near-duplicate removal using embeddings
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Loading SentenceTransformer on {device}...")
    model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
    
    texts = [r.comment for r in unique_exact]
    print(f"Computing embeddings for {len(texts)} texts...")
    t0 = time.time()
    embeddings = model.encode(texts, convert_to_tensor=True, batch_size=64)
    print(f"Embeddings computed in {time.time()-t0:.2f} seconds.")
    
    # We can do a greedy clustering / near-duplicate removal
    # If a text has >0.90 similarity to any already-kept text, we drop it.
    # To do this efficiently:
    kept_indices = []
    kept_embeddings = []
    
    threshold = 0.90
    
    print(f"Filtering near-duplicates at threshold {threshold}...")
    t0 = time.time()
    
    for i, emb in enumerate(embeddings):
        if not kept_embeddings:
            kept_embeddings.append(emb)
            kept_indices.append(i)
            continue
            
        # Stack kept embeddings to compare against current emb
        # shape: (num_kept, embedding_dim)
        stacked = torch.stack(kept_embeddings)
        
        # Compute cosine similarity
        sims = util.cos_sim(emb.unsqueeze(0), stacked)[0]
        
        if sims.max().item() < threshold:
            kept_embeddings.append(emb)
            kept_indices.append(i)
            
    print(f"Near-duplicate filtering completed in {time.time()-t0:.2f} seconds.")
    print(f"\nFinal count after near-duplicate removal: {len(kept_indices)} out of {len(unique_exact)}")
    print(f"Dropped {len(unique_exact) - len(kept_indices)} near-identical reviews.")

if __name__ == "__main__":
    main()
