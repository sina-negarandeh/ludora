import time
import argparse
import re
from datetime import datetime, timezone
import mlflow

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from sqlalchemy import text
from app.database.session import SessionLocal
from app.database.models import Review
from app.core.ml_config import ABSAConfig
from app.core.mlflow_utils import tracked_run

# The 22 Aspects strictly allowed
TAXONOMY = ABSAConfig.TAXONOMY

def extract_sentence(text_val, aspect):
    """Fallback to extract the sentence containing the aspect."""
    # Simple split by punctuation
    sentences = re.split(r'(?<=[.!?]) +', text_val.replace('\n', ' '))
    for s in sentences:
        if aspect.lower() in s.lower():
            return s.strip()
    return ""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None, help='Max reviews to process this run (omit to process all eligible reviews)')
    parser.add_argument('--minutes', type=float, default=None, help='Stop after roughly this many minutes of wall-clock processing, leaving the run resumable (skips already-processed reviews next time). Checked once per review, so a run stops shortly after the budget, not exactly at it.')
    parser.add_argument('--game_id', type=int, default=None, help='Restrict to a single BGG ID (for testing)')
    args = parser.parse_args()

    # Two separate sessions/connections: yield_per() below puts the read
    # session in server-side-cursor (stream_results) mode, and writing on
    # that same connection while the cursor is open invalidates it
    # (psycopg.errors.InvalidCursorName) — same issue already hit and fixed
    # in filter_eligible_reviews.py.
    read_db = SessionLocal()
    write_db = SessionLocal()

    device = torch.device("mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu"))
    print(f"Loading DeBERTa ABSA model ({ABSAConfig.MODEL_NAME}) on device: {device} ...")

    model_name = ABSAConfig.MODEL_NAME
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name).to(device)
    model.eval()

    label_map = {0: "negative", 1: "neutral", 2: "positive"}

    # Resume support at the *review* level via reviews.absa_processed_at,
    # set on every review this script runs inference on -- NOT derived from
    # review_aspects.review_id, which only reflects reviews that produced at
    # least one evidence-matched aspect. A review can be legitimately
    # attempted and yield zero storable aspects (no literal aspect-word
    # sentence match); treating "has a review_aspects row" as "was
    # processed" silently re-ran those reviews' inference on every
    # subsequent --minutes-bounded session, wasting more compute each time
    # as the unmarked backlog grew.
    #
    # Eligibility is a real DB column (scripts/filter_eligible_reviews.py),
    # not a JSON cache. Highest quality_score first, so an interrupted run
    # leaves the best reviews processed, not an arbitrary prefix.
    query = read_db.query(Review).filter(
        Review.is_absa_eligible.is_(True),
        Review.absa_processed_at.is_(None),
    )
    if args.game_id:
        query = query.filter(Review.game_id == args.game_id)
    query = query.order_by(Review.quality_score.desc())
    reviews = query.yield_per(1000)

    total_aspects_found = 0
    total_reviews_processed = 0
    start_time = time.time()

    with torch.no_grad():
        for r in reviews:
            if args.limit and total_reviews_processed >= args.limit:
                break
            if args.minutes and (time.time() - start_time) >= args.minutes * 60:
                print(f"\nTime budget of {args.minutes} min reached — stopping (resumable next run).")
                break

            text_val = r.comment
            batch_params = []
            BATCH_SIZE = ABSAConfig.BATCH_SIZE

            # Process the 22 aspects in chunks to bound peak GPU/MPS memory.
            for chunk_start in range(0, len(TAXONOMY), BATCH_SIZE):
                aspect_chunk = TAXONOMY[chunk_start:chunk_start + BATCH_SIZE]
                texts_chunk = [text_val] * len(aspect_chunk)

                inputs = tokenizer(texts_chunk, aspect_chunk, return_tensors="pt", padding=True, truncation=True, max_length=256).to(device)
                outputs = model(**inputs)
                probs_chunk = torch.softmax(outputs.logits, dim=1)

                for idx, aspect in enumerate(aspect_chunk):
                    prob_neg = probs_chunk[idx][0].item()
                    prob_neu = probs_chunk[idx][1].item()
                    prob_pos = probs_chunk[idx][2].item()

                    # Determine winner
                    winner_idx = probs_chunk[idx].argmax().item()
                    winner_label = label_map.get(winner_idx, "neutral")
                    winner_prob = probs_chunk[idx][winner_idx].item()

                    # Store every winning prediction -- positive, negative,
                    # AND neutral -- with its confidence, rather than
                    # filtering at extraction time. review_aspects becomes
                    # the complete raw record of what the classifier said;
                    # any confidence/sentiment threshold used for display or
                    # aggregation (ABSAConfig.WINNER_PROB_THRESHOLD, applied
                    # in absa_aggregate.py) becomes a query-time decision
                    # instead, freely revisable without ever re-running the
                    # ~4h classification pass again.
                    evidence = extract_sentence(text_val, aspect)
                    if evidence:
                        sentiment_score = prob_pos - prob_neg

                        batch_params.append({
                            "review_id": r.id,
                            "game_id": r.game_id,
                            "aspect": aspect,
                            "sentiment": winner_label,
                            "sentiment_score": sentiment_score,
                            "confidence": winner_prob,
                            "prob_positive": prob_pos,
                            "prob_neutral": prob_neu,
                            "prob_negative": prob_neg,
                            "evidence": evidence,
                            "model_used": ABSAConfig.MODEL_NAME,
                            "prompt_version": "hf_zero_shot",
                            "extracted_at": datetime.now(timezone.utc).replace(tzinfo=None)
                        })

            if batch_params:
                write_db.execute(text("""
                    INSERT INTO review_aspects (review_id, game_id, aspect, sentiment, sentiment_score, confidence, prob_positive, prob_neutral, prob_negative, evidence, model_used, prompt_version, extracted_at)
                    VALUES (:review_id, :game_id, :aspect, :sentiment, :sentiment_score, :confidence, :prob_positive, :prob_neutral, :prob_negative, :evidence, :model_used, :prompt_version, :extracted_at)
                """), batch_params)
                total_aspects_found += len(batch_params)

            # Mark the review as attempted regardless of yield -- a review
            # with zero evidence-matched aspects is still genuinely done,
            # not "not yet processed" (see the resume-logic comment above).
            write_db.execute(
                text("UPDATE reviews SET absa_processed_at = :ts WHERE id = :rid"),
                {"ts": datetime.now(timezone.utc).replace(tzinfo=None), "rid": r.id}
            )
            write_db.commit()

            total_reviews_processed += 1
            if total_reviews_processed % 500 == 0:
                elapsed = time.time() - start_time
                rate = total_reviews_processed / elapsed
                print(f"Processed {total_reviews_processed} reviews ({rate:.2f} rev/sec, {elapsed/60:.1f} min elapsed)")

    read_db.close()
    write_db.close()

    elapsed = time.time() - start_time
    print("\n--- Extraction Complete ---")
    print(f"Processed {total_reviews_processed} reviews in {elapsed:.2f} seconds.")
    if total_reviews_processed > 0:
        print(f"Average time per review: {elapsed/total_reviews_processed:.3f} seconds/review.")
    print(f"Total aspects extracted: {total_aspects_found}")

    # Backlog status across all sessions, not just this one -- the point of
    # --minutes runs is picking this back up later, so always report where
    # the whole job stands, not just what happened in this invocation.
    backlog_db = SessionLocal()
    total_eligible = backlog_db.execute(text("SELECT count(*) FROM reviews WHERE is_absa_eligible = true")).scalar()
    total_done = backlog_db.execute(text("SELECT count(*) FROM reviews WHERE is_absa_eligible = true AND absa_processed_at IS NOT NULL")).scalar()
    reviews_with_aspects = backlog_db.execute(text("SELECT count(DISTINCT review_id) FROM review_aspects WHERE review_id IS NOT NULL")).scalar()
    backlog_db.close()
    remaining = total_eligible - total_done
    print(f"\n--- Backlog status ---")
    print(f"{total_done}/{total_eligible} eligible reviews attempted overall ({remaining} remaining) — {reviews_with_aspects} of those yielded at least one storable aspect.")
    if remaining > 0 and total_reviews_processed > 0:
        rate = total_reviews_processed / elapsed
        eta_minutes = (remaining / rate) / 60
        print(f"At this session's rate (~{rate:.1f} rev/sec), ~{eta_minutes:.0f} more minutes to finish the backlog.")

    mlflow.log_params({
        "model_name": ABSAConfig.MODEL_NAME,
        "taxonomy_size": len(TAXONOMY),
        "batch_size": ABSAConfig.BATCH_SIZE,
        "quality_score_threshold": ABSAConfig.QUALITY_SCORE_THRESHOLD,
        "game_id_filter": args.game_id,
        "limit": args.limit,
        "minutes_budget": args.minutes,
    })
    mlflow.log_metrics({
        "total_aspects_extracted": total_aspects_found,
        "total_reviews_processed": total_reviews_processed,
        "elapsed_seconds": elapsed,
        "backlog_remaining": remaining,
    })

if __name__ == "__main__":
    with tracked_run("reviews/absa", run_name="extract"):
        main()
