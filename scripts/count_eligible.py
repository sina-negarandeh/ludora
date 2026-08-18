import os

from app.database.session import SessionLocal
from app.database.models import Review
from absa_extract_hf import compute_quality_score
import fasttext

def main():
    base_dir = os.path.dirname(__file__)
    ft_model_path = os.path.join(base_dir, '../data/models/lid.176.ftz')
    print("Loading fastText model...")
    ft_model = fasttext.load_model(ft_model_path)
    
    db = SessionLocal()
    game_id = 224517
    
    print(f"Fetching reviews for Brass: Birmingham (ID {game_id})...")
    total_reviews = db.query(Review).filter(Review.game_id == game_id).count()
    print(f"Total reviews in DB for this game: {total_reviews}")
    
    reviews = db.query(Review).filter(Review.game_id == game_id).yield_per(1000)
    
    eligible_06 = 0
    eligible_07 = 0
    eligible_08 = 0
    eligible_09 = 0
    total_processed = 0
    
    for r in reviews:
        if r.comment:
            q_score = compute_quality_score(r.comment, ft_model)
            if q_score >= 0.6: eligible_06 += 1
            if q_score >= 0.7: eligible_07 += 1
            if q_score >= 0.8: eligible_08 += 1
            if q_score >= 0.9: eligible_09 += 1
        total_processed += 1
        if total_processed % 5000 == 0:
            print(f"Processed {total_processed}...")
            
    print(f"\nFinal count for 5157 total reviews:")
    print(f">= 0.6: {eligible_06} reviews ({(eligible_06/total_reviews)*100:.1f}%)")
    print(f">= 0.7: {eligible_07} reviews ({(eligible_07/total_reviews)*100:.1f}%)")
    print(f">= 0.8: {eligible_08} reviews ({(eligible_08/total_reviews)*100:.1f}%)")
    print(f">= 0.9: {eligible_09} reviews ({(eligible_09/total_reviews)*100:.1f}%)")

if __name__ == "__main__":
    main()
