# Aspect-based sentiment analysis — DeBERTa zero-shot

**Category:** Reviews NLP · **Status:** Implemented, covers 100 games / ~10,000 reviews (not catalog-wide)

## Data

- Source: `reviews` table, filtered to a stratified sample.
- Sampling script: `scripts/generate_stratified_sample.py` — for the top-ranked games, scores every review's quality (see below), keeps only quality-eligible reviews, dedupes to one best review per user, buckets by rating into positive/mixed/negative, and proportionally allocates up to a target count per game. Output: `data/stratified_samples.json` (a game-id → review-id list cache).
- Quality/eligibility filter (`compute_quality_score`, shared by `scripts/absa_extract_hf.py`, `absa_filter.py`, `generate_stratified_sample.py`): fastText language confidence (English only) + review length (normalized) + a game-domain keyword bonus − a repeated-character spam penalty.

## Model / Architecture

`yangheng/deberta-v3-large-absa-v1.1` (HuggingFace) — a pretrained zero-shot aspect-based sentiment classifier, used purely for inference (sentence-pair classification: `(review_text, aspect)` → {negative, neutral, positive}). Every eligible review is classified against all 22 fixed taxonomy aspects; only non-neutral predictions above a confidence threshold are kept, each with an evidence sentence extracted via regex sentence-matching.

fastText `lid.176.ftz` (language ID) is a second pretrained model used only for the quality-score's language-confidence component — not part of the sentiment classification itself.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::ABSAConfig`.

| Param | Value |
|---|---|
| `MODEL_NAME` | `yangheng/deberta-v3-large-absa-v1.1` |
| `TAXONOMY` | 22 fixed aspects (Gameplay, Mechanics, Strategy, Theme, Immersion, Replayability, Components, Artwork, Production Quality, Rulebook, Setup, Teardown, Learning Curve, Complexity, Downtime, Player Interaction, Balance, Luck, Player Count, Solo Play, Game Length, Value) |
| `BATCH_SIZE` (aspects classified per chunk, to bound peak memory) | 11 |
| `WINNER_PROB_THRESHOLD` | 0.5 |
| `QUALITY_SCORE_THRESHOLD` (review eligibility) | 0.6 |
| `QUALITY_LENGTH_NORM_WORDS` | 100 |
| `QUALITY_SPAM_PENALTY` | 0.5 |
| `QUALITY_ASPECT_SIGNAL_CAP` / `_STEP` | 0.4 / 0.1 |
| `SAMPLE_TOP_N_GAMES` | 100 |
| `SAMPLE_TARGET_PER_GAME` | 100 |

No random seed needed for the classifier itself (deterministic inference). The superseded pilot script (`absa_filter.py`'s earlier sibling) used `random_state=42` for a one-off `df.sample()`, not part of the current pipeline.

## Training

None — `yangheng/deberta-v3-large-absa-v1.1` is used off-the-shelf, zero-shot, no fine-tuning against Ludora's own data.

- Scripts, in order: `scripts/generate_stratified_sample.py` → `scripts/absa_extract_hf.py --sampled` → `scripts/absa_aggregate.py`.
- Commands:
  ```bash
  uv run --project backend python scripts/generate_stratified_sample.py
  uv run --project backend python scripts/absa_extract_hf.py --sampled
  uv run --project backend python scripts/absa_aggregate.py
  ```
- MLflow experiment: `reviews/absa` (run names `stratified_sample`, `extract`, `aggregate`) — logs taxonomy size, thresholds, batch size, sample counts, and (for extraction) total aspects extracted + elapsed time.
- A distinct, earlier/pilot quality-filtering path (`scripts/absa_filter.py`, CSV-based over `master_reviews.csv`, not DB-based) logs under the same `reviews/absa` experiment (run name `pilot_filter`) — kept as a separate run since it's a different, non-canonical path, not a separate experiment.

## Artifact

None trained/saved for the DeBERTa model itself (pretrained weights, downloaded from HuggingFace at runtime). `data/models/lid.176.ftz` (938 KB) is the pinned fastText language-ID model, a plain download, not a trained artifact — its download is now atomic (temp-file + rename) so an interrupted download can never leave a corrupt file that a later run mistakes for "already downloaded."

## Evaluation

**Status: does not exist.** No ground-truth aspect-sentiment annotation set exists anywhere in this repo — there's no automated way to check whether a given (review, aspect) → sentiment prediction is correct. The DeBERTa model's own reported benchmark performance (from its model card on HuggingFace) is the only external signal available; nothing here validates it against Ludora's specific review corpus. This is a real, disclosed gap, not an oversight.

## Known limitations

- Covers only the top 100 ranked games / ~10,000 sampled reviews, not the ~4.2M-review corpus.
- No accuracy evaluation exists (see above).
- Two superseded implementation attempts exist in git history (an earlier Ollama + `qwen2.5:7b` generative-extraction approach, `scripts/absa_extract.py`, removed in this session's cleanup pass) — see `docs/ml/absa.md` for the two-implementation history.
