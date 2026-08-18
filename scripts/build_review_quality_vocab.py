"""One-time corpus-statistics pass for the review quality filter.

Derives two artifacts from a sample of the review corpus:
  1. Domain vocabulary CANDIDATES — frequent, non-stopword (stemmed) terms,
     written out for human curation, not auto-applied. Raw frequency alone
     surfaces generic praise words ("game", "fun", "great") ahead of
     specific ones ("meeple", "worker-placement", "rulebook") — see
     docs/ml/model-cards/absa-deberta.md for why this needs a human pass
     rather than a purely statistical cutoff.
  2. Boilerplate n-grams — phrases repeated across ABSAConfig.BOILERPLATE_MIN_COUNT
     or more *different* reviews. Applied by frequency threshold alone, no
     curation needed: an n-gram reused across hundreds of different users'
     reviews is unambiguously templated filler regardless of judgment calls,
     unlike single-word vocabulary.

Usage:
    uv run --project backend python scripts/build_review_quality_vocab.py
"""
import argparse
import json
import os
from collections import Counter

from sqlalchemy import func

from app.database.session import SessionLocal
from app.database.models import Review
from app.core.ml_config import ABSAConfig
from app.core.review_quality import tokenize, STOPWORDS, stem


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample_size", type=int, default=200_000)
    parser.add_argument("--top_n_vocab", type=int, default=300)
    args = parser.parse_args()

    db = SessionLocal()

    print(f"Sampling {args.sample_size} English reviews...")
    rows = (
        db.query(Review.comment)
        .filter(Review.language == "en", Review.comment.isnot(None))
        .order_by(func.random())
        .limit(args.sample_size)
        .all()
    )
    print(f"Loaded {len(rows)} reviews.")

    ngram_n = ABSAConfig.BOILERPLATE_NGRAM_SIZE
    term_counts = Counter()
    ngram_counts = Counter()

    for i, (comment,) in enumerate(rows):
        tokens = tokenize(comment)

        # Vocabulary candidates: stemmed, non-stopword, non-numeric —
        # consolidates word forms ("component"/"components") before ranking.
        for t in tokens:
            if t not in STOPWORDS and len(t) > 2 and not t.isdigit():
                term_counts[stem(t)] += 1

        # Boilerplate: raw (unstemmed) n-grams — we want literal repeated
        # phrasing here, not stemmed-and-blurred phrasing.
        for j in range(len(tokens) - ngram_n + 1):
            ngram_counts[tuple(tokens[j:j + ngram_n])] += 1

        if (i + 1) % 50_000 == 0:
            print(f"  processed {i + 1}/{len(rows)}...")

    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)

    vocab_path = os.path.join(out_dir, "review_quality_vocab_candidates.txt")
    candidates = term_counts.most_common(args.top_n_vocab)
    with open(vocab_path, "w") as f:
        for term, count in candidates:
            f.write(f"{term}\t{count}\n")
    print(f"\nWrote {len(candidates)} vocabulary candidates to {vocab_path} (for human curation).")

    boilerplate = {gram for gram, count in ngram_counts.items() if count >= ABSAConfig.BOILERPLATE_MIN_COUNT}
    boilerplate_path = os.path.join(out_dir, "boilerplate_ngrams.json")
    with open(boilerplate_path, "w") as f:
        json.dump([list(g) for g in boilerplate], f)
    print(f"Flagged {len(boilerplate)} boilerplate {ngram_n}-grams (>= {ABSAConfig.BOILERPLATE_MIN_COUNT} occurrences) -> {boilerplate_path}")

    if boilerplate:
        print("\nSample boilerplate phrases:")
        for gram in list(boilerplate)[:10]:
            print(f"  {' '.join(gram)!r} (count={ngram_counts[gram]})")


if __name__ == "__main__":
    main()
