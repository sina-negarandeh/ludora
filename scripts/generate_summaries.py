import argparse
import json
import time

import mlflow
from sqlalchemy import text

from app.database.session import SessionLocal
from app.services.summarization_service import SummarizationService
from app.database.models import Game
from app.core.config import settings
from app.core.ml_config import RANDOM_SEED, SummarizationConfig
from app.core.mlflow_utils import tracked_run

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game_id', type=int, default=None, help='Restrict to a single BGG ID (for testing)')
    parser.add_argument('--limit', type=int, default=None, help='Max games to process this run')
    parser.add_argument('--minutes', type=float, default=None, help='Stop after roughly this many minutes of wall-clock processing, leaving the run resumable')
    args = parser.parse_args()

    with SessionLocal() as db:
        # Resumability: a game is done once it has a game_summaries row.
        # Unlike ABSA extraction, there's no ambiguous "attempted but empty"
        # state to track separately here -- every case that leaves a game
        # without a row (not yet eligible, or a transient LLM failure even
        # after SummarizationService's internal retries) is exactly a case
        # that SHOULD be retried on a future run, so "skip only if a row
        # already exists" is correct on its own, no extra tracking column
        # needed. Eligibility is also a moving target (grows as more of the
        # ABSA backlog completes), so re-checking it each run is deliberate,
        # not wasted work -- it's a cheap SQL query, not an LLM call.
        already_done = {r[0] for r in db.execute(text("SELECT game_id FROM game_summaries")).fetchall()}
        print(f"{len(already_done)} games already summarized — will be skipped.")

        if args.game_id:
            candidate_ids = [args.game_id]
        else:
            # Cheap first-pass filter -- games with at least one aspect past
            # the display floor. generate_game_summary() does the precise
            # eligibility check (including the distinct-qualifying-review
            # count) per game and returns None if it's not actually
            # eligible; this just avoids querying every one of the ~28K
            # catalog games when most have no ABSA data yet.
            rows = db.execute(text("""
                SELECT DISTINCT game_id FROM game_aspect_aggregates
                WHERE total_mentions >= :min_mentions
                ORDER BY game_id
            """), {"min_mentions": SummarizationConfig.MIN_ASPECT_MENTIONS}).fetchall()
            candidate_ids = [r[0] for r in rows if r[0] not in already_done]

        print(f"{len(candidate_ids)} candidate games to attempt this run.")

        mlflow.log_params({
            "llm_model": settings.SUMMARIZATION_MODEL_NAME,
            "temperature": SummarizationConfig.TEMPERATURE,
            "min_reviews_for_absa": SummarizationConfig.MIN_REVIEWS_FOR_ABSA,
            "min_aspect_mentions": SummarizationConfig.MIN_ASPECT_MENTIONS,
            "top_k_aspects": SummarizationConfig.TOP_K_ASPECTS,
            "max_reviews_per_aspect": SummarizationConfig.MAX_REVIEWS_PER_ASPECT,
            "max_llm_retries": SummarizationConfig.MAX_LLM_RETRIES,
            "random_seed": RANDOM_SEED,
            "game_id_filter": args.game_id,
            "limit": args.limit,
            "minutes_budget": args.minutes,
        })

        summarizer = SummarizationService(db)

        generated = 0
        skipped_ineligible = 0
        failed = 0
        start_time = time.time()

        for i, game_id in enumerate(candidate_ids):
            if args.limit and (generated + skipped_ineligible + failed) >= args.limit:
                break
            if args.minutes and (time.time() - start_time) >= args.minutes * 60:
                print(f"\nTime budget of {args.minutes} min reached — stopping (resumable next run).")
                break

            game = db.query(Game).filter(Game.bgg_id == game_id).first()
            if not game:
                continue

            print(f"[{i + 1}/{len(candidate_ids)}] {game.name} (BGG ID: {game_id})")
            try:
                result = summarizer.generate_game_summary(game_id)
            except Exception as e:
                # A single game's unexpected failure must never abort an
                # unattended batch run over thousands of games.
                print(f"  ERROR: {e}")
                failed += 1
                continue

            if result:
                generated += 1
                print(f"  -> {result.summary}")
            else:
                skipped_ineligible += 1

        elapsed = time.time() - start_time

        print("\n--- Batch complete ---")
        print(f"Generated: {generated}, skipped (ineligible or exhausted retries): {skipped_ineligible}, failed (unexpected error): {failed}")
        print(f"Elapsed: {elapsed:.1f}s" + (f" ({elapsed / generated:.1f}s/game generated)" if generated else ""))
        print("Note: the eligible-candidate count is a moving target that grows as more of the ABSA classification backlog completes — this is not a fixed total the way ABSA's eligible-review count is.")

        # LLM-prompted features don't have conventional hyperparameters —
        # what actually determines behavior is the prompt + model, so
        # that's what gets logged here, aggregated across the whole batch.
        if summarizer.llm_calls:
            latencies = [c["latency_seconds"] for c in summarizer.llm_calls]
            failed_calls = sum(1 for c in summarizer.llm_calls if c.get("failed"))
            mlflow.log_metrics({
                "llm_call_count": len(summarizer.llm_calls),
                "llm_call_failed_count": failed_calls,
                "total_llm_latency_seconds": round(sum(latencies), 3),
                "avg_llm_latency_seconds": round(sum(latencies) / len(latencies), 3),
                "max_llm_latency_seconds": round(max(latencies), 3),
            })
            mlflow.log_text(json.dumps(summarizer.llm_calls, indent=2), "llm_calls.json")

        mlflow.log_metrics({
            "games_generated": generated,
            "games_skipped_ineligible": skipped_ineligible,
            "games_failed": failed,
            "games_already_done_before_run": len(already_done),
            "elapsed_seconds": elapsed,
        })

if __name__ == "__main__":
    with tracked_run("llm/review_summarization", run_name="generate_batch"):
        main()
