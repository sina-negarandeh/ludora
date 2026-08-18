import os
import pandas as pd
import mlflow
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

from app.database.models import Game, GameRecommendation
from app.core.config import settings
from app.core.ml_config import RecommenderConfig
from app.core.mlflow_utils import tracked_run
from app.recommenders.collaborative.item_cosine import ItemCosineRecommender
from app.recommenders.collaborative.svd import SVDRecommender
from app.recommenders.collaborative.als import ALSRecommender

def main():
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Fetching games from DB...")
    games = session.query(Game.bgg_id).all()
    valid_game_ids = {g[0] for g in games}
    print(f"Loaded {len(valid_game_ids)} valid games from DB.")

    if not valid_game_ids:
        print("No games in database. Exiting.")
        return

    csv_path = os.path.join(os.path.dirname(__file__), '../data/raw/user_ratings.csv')
    print(f"Loading user ratings from {csv_path}...")
    
    # chunksize might be needed if memory is an issue, but we'll try loading it all
    # using appropriate dtypes to save memory
    df = pd.read_csv(
        csv_path, 
        usecols=['BGGId', 'Rating', 'Username'],
        dtype={'BGGId': 'int32', 'Rating': 'float32', 'Username': 'category'}
    )
    df.rename(columns={'BGGId': 'item', 'Rating': 'rating', 'Username': 'user'}, inplace=True)

    print(f"Original ratings shape: {df.shape}")
    
    # Filter to valid games only and drop NaNs
    df = df[df['item'].isin(valid_game_ids)]
    df = df.dropna(subset=['user', 'item', 'rating'])
    print(f"Filtered ratings shape (valid games only): {df.shape}")

    # Initialize models
    recommenders = [
        ItemCosineRecommender(min_shared_users=RecommenderConfig.CF_ITEM_COSINE_MIN_SHARED_USERS),
        SVDRecommender(n_factors=RecommenderConfig.CF_SVD_N_FACTORS),
        ALSRecommender(
            factors=RecommenderConfig.CF_ALS_FACTORS,
            iterations=RecommenderConfig.CF_ALS_ITERATIONS,
            regularization=RecommenderConfig.CF_ALS_REGULARIZATION,
        ),
    ]

    for recommender in recommenders:
        model_name = recommender.get_model_name()
        print(f"\n--- Processing model: {model_name} ---")

        with tracked_run("recommender/collaborative", run_name=f"{model_name}_precompute"):
            # Only the scalar hyperparameters set in __init__ — vars() also
            # holds the (currently unfitted) similarity matrix/dict attrs.
            hyperparams = {k: v for k, v in vars(recommender).items() if isinstance(v, (int, float, str, bool))}
            mlflow.log_params({
                **hyperparams,
                "n_ratings": len(df),
                "n_valid_games": len(valid_game_ids),
            })

            print("Fitting model...")
            recommender.fit(df)

            print("Clearing old recommendations for this model...")
            session.query(GameRecommendation).filter(GameRecommendation.model == model_name).delete()
            session.commit()

            print("Generating recommendations...")
            recs_to_insert = []
            batch_size = 5000
            count = 0
            total_recs = 0

            for bgg_id in valid_game_ids:
                recs = recommender.recommend(item_id=bgg_id, limit=RecommenderConfig.RECS_PER_MODEL_LIMIT)

                for rec in recs:
                    recs_to_insert.append({
                        'game_id': bgg_id,
                        'recommended_game_id': rec['item_id'],
                        'model': model_name,
                        'score': rec['score'],
                        'reasons': []  # User requested to leave reasons empty for now
                    })

                count += 1
                if count % 1000 == 0:
                    print(f"Processed {count}/{len(valid_game_ids)} games")

                if len(recs_to_insert) >= batch_size:
                    stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
                        index_elements=['game_id', 'recommended_game_id', 'model']
                    )
                    session.execute(stmt)
                    session.commit()
                    total_recs += len(recs_to_insert)
                    recs_to_insert = []

            # Insert remaining
            if recs_to_insert:
                stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
                    index_elements=['game_id', 'recommended_game_id', 'model']
                )
                session.execute(stmt)
                session.commit()
                total_recs += len(recs_to_insert)

            mlflow.log_metrics({"games_processed": count, "recommendations_written": total_recs})

        print(f"Finished {model_name}!")

if __name__ == "__main__":
    main()
