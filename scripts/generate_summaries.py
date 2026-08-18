import json

import mlflow

from app.database.session import SessionLocal
from app.services.summarization_service import SummarizationService
from app.database.models import Game
from app.core.config import settings
from app.core.ml_config import RANDOM_SEED, SummarizationConfig
from app.core.mlflow_utils import tracked_run

# Known limitation: hardcodes a single game — there is no batch/loop-over-
# all-eligible-games invocation in this pipeline yet.
GAME_NAME = "Brass: Birmingham"

def main():
    with SessionLocal() as db:
        game = db.query(Game).filter(Game.name == GAME_NAME).first()
        if not game:
            print(f"Game '{GAME_NAME}' not found.")
            return

        print(f"Found game: {game.name} (BGG ID: {game.bgg_id})")
        print("Initializing Summarization Service...")

        mlflow.log_params({
            "game_id": game.bgg_id,
            "game_name": game.name,
            "llm_model": settings.LLM_MODEL_NAME,
            "temperature": SummarizationConfig.TEMPERATURE,
            "min_reviews_for_absa": SummarizationConfig.MIN_REVIEWS_FOR_ABSA,
            "min_aspect_mentions": SummarizationConfig.MIN_ASPECT_MENTIONS,
            "top_k_aspects": SummarizationConfig.TOP_K_ASPECTS,
            "max_reviews_per_aspect": SummarizationConfig.MAX_REVIEWS_PER_ASPECT,
            "random_seed": RANDOM_SEED,
        })

        summarizer = SummarizationService(db)
        summary_obj = summarizer.generate_game_summary(game.bgg_id)

        # LLM-prompted features don't have conventional hyperparameters — what
        # actually determines behavior is the prompt + model, so that's what
        # gets logged here instead: a hash per distinct prompt used (one for
        # each aspect mini-summary, one for the final synthesis) and latency,
        # rather than pretending this is a trained model with a fit config.
        if summarizer.llm_calls:
            latencies = [c["latency_seconds"] for c in summarizer.llm_calls]
            mlflow.log_metrics({
                "llm_call_count": len(summarizer.llm_calls),
                "total_llm_latency_seconds": round(sum(latencies), 3),
                "avg_llm_latency_seconds": round(sum(latencies) / len(latencies), 3),
                "max_llm_latency_seconds": round(max(latencies), 3),
            })
            mlflow.log_text(json.dumps(summarizer.llm_calls, indent=2), "llm_calls.json")
            mlflow.log_params({f"prompt_hash_{c['schema']}": c["prompt_hash"] for c in summarizer.llm_calls})

        if summary_obj:
            print("\n" + "="*50)
            print("FINAL CUSTOMERS SAY SUMMARY:")
            print("="*50)
            print(summary_obj.summary)
            mlflow.log_metrics({"generated": 1})
        else:
            print(f"Failed to generate summary for {game.name}.")
            mlflow.log_metrics({"generated": 0})

if __name__ == "__main__":
    with tracked_run("llm/review_summarization", run_name="generate"):
        main()
