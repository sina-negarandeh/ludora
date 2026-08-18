from sqlalchemy import text
import mlflow

from app.database.session import SessionLocal
from app.core.mlflow_utils import tracked_run

def main():
    print("Aggregating aspect sentiments into game_aspect_aggregates...")
    db = SessionLocal()


    # Simple INSERT ... ON CONFLICT DO UPDATE
    # Aggregating all review_aspects into game_aspect_aggregates
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
        COUNT(CASE WHEN sentiment = 'mixed' THEN 1 END) as mixed_count,
        COUNT(CASE WHEN sentiment = 'neutral' THEN 1 END) as neutral_count,
        COUNT(*) as total_mentions,
        AVG(sentiment_score) as mean_sentiment
    FROM review_aspects
    GROUP BY game_id, aspect
    ON CONFLICT (game_id, aspect) DO UPDATE SET
        positive_count = EXCLUDED.positive_count,
        negative_count = EXCLUDED.negative_count,
        mixed_count = EXCLUDED.mixed_count,
        neutral_count = EXCLUDED.neutral_count,
        total_mentions = EXCLUDED.total_mentions,
        mean_sentiment = EXCLUDED.mean_sentiment;
    """
    
    db.execute(text(sql))
    db.commit()

    row_count = db.execute(text("SELECT COUNT(*) FROM game_aspect_aggregates")).scalar()
    mlflow.log_metrics({"aggregate_rows": row_count})
    print("Aggregation complete!")

if __name__ == "__main__":
    with tracked_run("reviews/absa", run_name="aggregate"):
        main()
