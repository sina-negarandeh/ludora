import os

import mlflow
from sqlalchemy import text
from app.database.session import SessionLocal
from app.recommenders.collaborative.svd import SVDRecommender
from app.core.mlflow_utils import tracked_run

def main():
    print("Connecting to database...")
    db = SessionLocal()

    print("Loading SVD Model...")
    model_path = os.path.join(os.path.dirname(__file__), '../data/models/cf_svd.pkl')

    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}")
        return

    model = SVDRecommender()
    model.load(model_path)
    print("Model loaded successfully.")
    mlflow.log_params({"n_factors": model.n_factors, "model_path": model_path})

    print("Fetching game IDs...")
    games = db.execute(text("SELECT bgg_id FROM games")).fetchall()

    # Delete old recommendations for cf_svd
    print("Clearing old cf_svd recommendations...")
    db.execute(text("DELETE FROM game_recommendations WHERE model = 'cf_svd'"))
    db.commit()

    print("Generating recommendations for all games...")
    batch_params = []

    count = 0
    for game in games:
        bgg_id = game[0]
        recs = model.recommend(item_id=bgg_id, limit=20)
        
        for r in recs:
            batch_params.append({
                "game_id": bgg_id,
                "recommended_game_id": r['item_id'],
                "model": "cf_svd",
                "score": float(r['score']),
                "reasons": '["High collaborative similarity"]' # JSON string
            })
            
        count += 1
        if count % 1000 == 0:
            print(f"Processed {count}/{len(games)} games...")
            if batch_params:
                db.execute(text("""
                    INSERT INTO game_recommendations (game_id, recommended_game_id, model, score, reasons)
                    VALUES (:game_id, :recommended_game_id, :model, :score, :reasons::json)
                """), batch_params)
                db.commit()
                batch_params = []
                
    # Insert any remaining
    if batch_params:
        db.execute(text("""
            INSERT INTO game_recommendations (game_id, recommended_game_id, model, score, reasons)
            VALUES (:game_id, :recommended_game_id, :model, :score, :reasons::json)
        """), batch_params)
        db.commit()

    mlflow.log_metrics({"games_processed": count})
    print("Finished precomputing SVD recommendations!")

if __name__ == "__main__":
    with tracked_run("recommender/collaborative", run_name="cf_svd_precompute_from_pickle"):
        main()
