"""Filter the full review corpus for ABSA eligibility — replaces the old
top-100-games / 100-per-game / 10K-cap sampling scheme (scripts/generate_stratified_sample.py,
deleted). The quality filter (app.core.review_quality) is cheap enough to
run over the entire ~4.2M-review corpus directly (measured ~5 minutes),
so there's no need to pre-restrict to a subset of games or games ranked by
popularity, or artificially cap the total count — every review gets a real
chance to qualify, and `absa_extract_hf.py` reads eligibility straight off
`reviews.is_absa_eligible` instead of a JSON cache.

Near-duplicate detection at this scale needs bucketing: comparing every
candidate against every previously-seen fingerprint (as the old per-game
script did) is O(n^2), fine for a few thousand reviews in one game, not for
hundreds of thousands globally. Bucketing by the top 16 bits of the 64-bit
SimHash fingerprint bounds each comparison to same-bucket candidates only —
this will occasionally miss a near-duplicate pair whose difference happens
to fall in those top bits, a known, honest tradeoff for tractable runtime
at this scale, not a claim of perfect recall.

Note on pipeline order: dedup runs *after* the quality-score threshold, not
before. Language/hard filters and scoring are O(1) per review with no
growing state, but dedup needs to hold every previously-seen review's
fingerprint in memory — doing that for the ~3.2M reviews that pass language/
hard filters (most of the corpus) instead of the ~380K that also clear the
quality bar would inflate memory usage roughly 8-9x for no behavioral
difference (a review that's both a duplicate and below-threshold is
excluded either way; only which counter it's attributed to changes).

Usage:
    uv run --project backend python scripts/filter_eligible_reviews.py
"""
import hashlib
import time
from collections import defaultdict

from sqlalchemy import text
import mlflow

from app.database.session import SessionLocal
from app.core.ml_config import ABSAConfig
from app.core.mlflow_utils import tracked_run
from app.core.review_quality import (
    passes_language_filter, passes_hard_filters, compute_quality_score,
    normalize_for_dedup, tokenize, simhash, hamming_distance, load_boilerplate_ngrams,
)

# Bucket by the top 16 bits of the 64-bit fingerprint (bits 48-63).
_SIMHASH_BUCKET_SHIFT = 48
_UPDATE_BATCH_SIZE = 5000


def _simhash_bucket(fingerprint: int) -> int:
    return fingerprint >> _SIMHASH_BUCKET_SHIFT


def main():
    boilerplate_ngrams = load_boilerplate_ngrams()
    db = SessionLocal()
    engine = db.get_bind()

    total_scanned = 0
    total_lang_or_hard_filtered = 0
    total_exact_dupes = 0
    total_near_dupes = 0
    total_below_threshold = 0
    total_eligible = 0

    seen_exact = set()
    simhash_buckets = defaultdict(list)  # bucket -> [(fingerprint, review_id), ...]

    pending_updates = []
    start_time = time.time()

    print("Streaming all reviews (this scans the full corpus once)...")
    # Two separate connections: `read_conn` holds the server-side streaming
    # cursor (needed so 4.2M rows don't load into memory at once); `write_conn`
    # does the batched UPDATEs. psycopg doesn't support executemany on a
    # connection with an active server-side cursor, so these can't share one.
    with engine.connect() as read_conn, engine.connect() as write_conn:
        result = read_conn.execution_options(stream_results=True).execute(
            text("SELECT id, comment, language, language_confidence FROM reviews WHERE comment IS NOT NULL")
        )
        for row in result:
            review_id, comment, language, language_confidence = row
            total_scanned += 1

            if not passes_language_filter(language, language_confidence):
                total_lang_or_hard_filtered += 1
                continue
            if not passes_hard_filters(comment):
                total_lang_or_hard_filtered += 1
                continue

            # Score before dedup — see module docstring for why.
            score = compute_quality_score(comment, boilerplate_ngrams=boilerplate_ngrams)
            if score < ABSAConfig.QUALITY_SCORE_THRESHOLD:
                total_below_threshold += 1
                continue

            # Hash digest, not the raw normalized string — cheaper to hold
            # ~380K of these in memory than full review text.
            normalized_hash = hashlib.md5(normalize_for_dedup(comment).encode("utf-8")).hexdigest()
            if normalized_hash in seen_exact:
                total_exact_dupes += 1
                continue
            seen_exact.add(normalized_hash)

            tokens = tokenize(comment)
            fingerprint = simhash(tokens)
            bucket = _simhash_bucket(fingerprint)
            bucket_members = simhash_buckets[bucket]
            if any(
                hamming_distance(fingerprint, other_fp) <= ABSAConfig.QUALITY_SIMHASH_MAX_DISTANCE
                for other_fp, _ in bucket_members
            ):
                total_near_dupes += 1
                continue
            bucket_members.append((fingerprint, review_id))

            total_eligible += 1
            pending_updates.append({"id": review_id, "score": score})

            if len(pending_updates) >= _UPDATE_BATCH_SIZE:
                write_conn.execute(
                    text("UPDATE reviews SET is_absa_eligible = true, quality_score = :score WHERE id = :id"),
                    pending_updates,
                )
                write_conn.commit()
                pending_updates = []

            if total_scanned % 500_000 == 0:
                elapsed = time.time() - start_time
                print(f"  scanned {total_scanned}, eligible so far {total_eligible} ({elapsed:.0f}s elapsed)")

        if pending_updates:
            write_conn.execute(
                text("UPDATE reviews SET is_absa_eligible = true, quality_score = :score WHERE id = :id"),
                pending_updates,
            )
            write_conn.commit()

    elapsed = time.time() - start_time
    print(f"\n--- Filtering complete in {elapsed:.1f}s ---")
    print(f"Total reviews scanned: {total_scanned}")
    print(f"  Filtered by language/hard filters: {total_lang_or_hard_filtered}")
    print(f"  Exact duplicates skipped: {total_exact_dupes}")
    print(f"  Near duplicates skipped (bucketed SimHash): {total_near_dupes}")
    print(f"  Below quality threshold ({ABSAConfig.QUALITY_SCORE_THRESHOLD}): {total_below_threshold}")
    print(f"Total eligible for ABSA: {total_eligible}")

    mlflow.log_params({
        "quality_score_threshold": ABSAConfig.QUALITY_SCORE_THRESHOLD,
        "simhash_max_distance": ABSAConfig.QUALITY_SIMHASH_MAX_DISTANCE,
        "simhash_bucket_bits": 64 - _SIMHASH_BUCKET_SHIFT,
    })
    mlflow.log_metrics({
        "reviews_scanned": total_scanned,
        "filtered_language_or_hard": total_lang_or_hard_filtered,
        "filtered_exact_dupes": total_exact_dupes,
        "filtered_near_dupes": total_near_dupes,
        "filtered_below_threshold": total_below_threshold,
        "reviews_eligible": total_eligible,
        "elapsed_seconds": elapsed,
    })


if __name__ == "__main__":
    with tracked_run("reviews/absa", run_name="filter_eligible_reviews"):
        main()
