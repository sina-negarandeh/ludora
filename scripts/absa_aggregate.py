from sqlalchemy import text
import mlflow

from app.database.session import SessionLocal
from app.core.ml_config import ABSAConfig
from app.core.mlflow_utils import tracked_run

def main():
    print("Aggregating aspect sentiments into game_aspect_aggregates...")
    db = SessionLocal()

    # review_aspects now stores every winning prediction (positive/negative/
    # neutral, any confidence) -- scripts/absa_extract_hf.py no longer
    # filters at extraction time. This rollup applies the confidence bar
    # here instead (ABSAConfig.WINNER_PROB_THRESHOLD), uniformly across all
    # three sentiments -- the reviews-section card now has a Mixed/Neutral
    # state (AspectService.get_game_aspects(), GameDetail.tsx) driven by
    # neutral_count, not just positive/negative.
    sql = """
    INSERT INTO game_aspect_aggregates (
        game_id, aspect,
        positive_count, negative_count, mixed_count, neutral_count,
        total_mentions, mean_sentiment
    )
    SELECT
        game_id,
        aspect,
        COUNT(CASE WHEN sentiment = 'positive' THEN 1 END) as positive_count,
        COUNT(CASE WHEN sentiment = 'negative' THEN 1 END) as negative_count,
        0 as mixed_count,
        COUNT(CASE WHEN sentiment = 'neutral' THEN 1 END) as neutral_count,
        COUNT(*) as total_mentions,
        AVG(sentiment_score) as mean_sentiment
    FROM review_aspects
    WHERE sentiment IN ('positive', 'negative', 'neutral') AND confidence >= :threshold
    GROUP BY game_id, aspect
    ON CONFLICT (game_id, aspect) DO UPDATE SET
        positive_count = EXCLUDED.positive_count,
        negative_count = EXCLUDED.negative_count,
        mixed_count = EXCLUDED.mixed_count,
        neutral_count = EXCLUDED.neutral_count,
        total_mentions = EXCLUDED.total_mentions,
        mean_sentiment = EXCLUDED.mean_sentiment;
    """

    db.execute(text(sql), {"threshold": ABSAConfig.WINNER_PROB_THRESHOLD})
    db.commit()

    row_count = db.execute(text("SELECT COUNT(*) FROM game_aspect_aggregates")).scalar()
    mlflow.log_metrics({"aggregate_rows": row_count})
    mlflow.log_params({"winner_prob_threshold": ABSAConfig.WINNER_PROB_THRESHOLD})
    print("Aggregation complete!")

if __name__ == "__main__":
    with tracked_run("reviews/absa", run_name="aggregate"):
        main()
