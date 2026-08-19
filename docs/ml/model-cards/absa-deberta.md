# Aspect-based sentiment analysis: DeBERTa zero-shot

**Category:** Reviews NLP · **Status:** Eligibility computed over the full corpus; classification running in resumable chunks (39,484/267,950 eligible reviews attempted as of this writing)

## Data

- Source: `reviews` table, filtered for eligibility across the entire corpus (no pre-restriction to top-ranked games).
- Filtering script: `scripts/filter_eligible_reviews.py` streams all ~4.2M reviews once, applies `app.core.review_quality`'s pipeline (language gate, hard filters, dedup, weighted score), and persists the result directly on `reviews.is_absa_eligible`/`quality_score`.
- Quality and eligibility filter (`app.core.review_quality`): language gate reusing precomputed `reviews.language`/`language_confidence` (no live fastText call); hard filters (min chars/tokens, valid Unicode, has letters, detectable sentiment via NLTK's VADER lexicon); exact and bucketed-SimHash near-duplicate removal; a weighted score combining information density, lexical diversity, corpus-derived domain specificity, and a boilerplate-phrase penalty. See `docs/ml/absa.md#quality-and-eligibility-filtering-before-extraction` for the full design rationale, including a stopword-ratio filter that was tried and reverted after it wrongly rejected genuine short reviews.
- Measured against the real corpus: 267,950 of 4,208,067 reviews eligible (about 6.4%), computed in about 14 minutes.

## Model / Architecture

`yangheng/deberta-v3-base-absa-v1.1` (HuggingFace), a pretrained zero-shot aspect-based sentiment classifier, used purely for inference (sentence-pair classification: `(review_text, aspect)` → negative, neutral, or positive). The base checkpoint, not the larger one, chosen for speed and coverage; same trainer and ~180K-example training corpus (SemEval-2014/2016, MAMS), so the checkpoint size doesn't change the domain mismatch (restaurant/laptop reviews, not board games) discussed under Evaluation below. Every eligible review is classified against all 17 fixed taxonomy aspects (see [Taxonomy](#taxonomy) below). Every prediction with an evidence-matched sentence is stored, positive, negative, and neutral, at any confidence, with the full 3-class softmax; the confidence and sentiment threshold applies at aggregation, not extraction (see [Hyperparameters](#hyperparameters)), so it's revisable without re-running classification.

fastText `lid.176.ftz` (language ID) is still used, but only by `scripts/detect_languages.py` to populate `reviews.language`/`language_confidence` ahead of time; the ABSA pipeline itself reads those columns rather than calling fastText live. NLTK's VADER lexicon (also pretrained, not trained by us) is used as one of the hard-filter signals in `app.core.review_quality`.

## Taxonomy

17 aspects: Mechanics, Strategy, Theme, Replayability, Components, Artwork, Rulebook, Setup, Learning Curve, Complexity, Downtime, Player Interaction, Balance, Luck, Solo Play, Game Length, Value.

Reduced from an original 22. Dropped Gameplay (too broad, added no information beyond Mechanics, Strategy, Balance, and Player Interaction combined), Immersion (6 mentions versus Theme's 294 across the corpus, since reviewers don't distinguish "good theme" from "felt immersed," it's the same comment), Production Quality (a vaguer umbrella over the more specific, more-discussed Components and Artwork), Teardown (2 mentions in the entire eligible corpus), and Player Count (the wrong shape for a single sentiment score, since "great at 2, drags at 5" isn't one verdict, and redundant with the structured `suggested_num_players` poll data already shown elsewhere on the game page). Each removal was checked against real mention-frequency counts in the corpus, not decided by judgment alone.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::ABSAConfig`.

| Param | Value |
|---|---|
| `MODEL_NAME` | `yangheng/deberta-v3-base-absa-v1.1` |
| `TAXONOMY` | 17 aspects (see above) |
| `BATCH_SIZE` (aspects classified per forward pass) | 17, all aspects in one pass |
| `WINNER_PROB_THRESHOLD` (applied at aggregation, all 3 sentiments) | 0.7, chosen from a real probe (400-review sample): median winner confidence 0.991 positive, 0.968 negative, 0.843 neutral; a naive 0.5 value filters out almost nothing |
| `CARD_DOMINANCE_THRESHOLD` (UI card state) | 0.6; an aspect reads as confidently Positive/Negative only above this share, otherwise the card shows Mixed |
| `QUALITY_SCORE_THRESHOLD` (review eligibility) | 0.6, calibrated against a real 50K-review score distribution (p90 around 0.6), not guessed |
| `QUALITY_MIN_LANGUAGE_CONFIDENCE` | 0.5 |
| `QUALITY_MIN_CHARS` / `QUALITY_MIN_TOKENS` | 10 / 3 |
| `QUALITY_SIMHASH_BITS` / `QUALITY_SIMHASH_MAX_DISTANCE` | 64 / 3 |
| `QUALITY_DENSITY_WEIGHT` / `_DIVERSITY_WEIGHT` / `_SPECIFICITY_WEIGHT` / `_BOILERPLATE_WEIGHT` | 0.35 / 0.25 / 0.30 / 0.30 |
| `DOMAIN_VOCABULARY` | About 90 hand-curated, corpus-derived stems (see `scripts/build_review_quality_vocab.py`) |
| `BOILERPLATE_NGRAM_SIZE` / `BOILERPLATE_MIN_COUNT` | 4 / 50 |

No random seed needed; the classifier and the quality filter are both deterministic (no sampling, no training).

**Batching, measured.** `BATCH_SIZE=17` (all aspects per review in one forward pass) is the real optimum, not an untested default. `batch_size=11` (tuned for the larger checkpoint) measured 9.66 reviews/sec against the base checkpoint; batching all aspects in one pass measured 12.04 reviews/sec (about 20% faster), with no further gain from padding batches wider (44/88), since there's nothing more to batch once every aspect is included. Batching across different reviews was also tested and found to be dramatically worse, a projected 10.18h to 58.14h at 16 reviews per batch, because `padding=True` pads every sequence in a batch to the longest one present, so mixing reviews of different lengths wastes compute padding short reviews out to match long ones. Reducing aspect count also measurably speeds this up, roughly linear down to about 11 aspects, diminishing below that: a real lever, traded off against taxonomy coverage. The 22-to-17 reduction above was decided on its own merits, not chosen for speed, though it does help speed too.

**Investigated and ruled out.** ONNX quantization via HuggingFace's `optimum` library, blocked by a hard dependency conflict (`optimum` requires `transformers<4.58`; this project is on `transformers>=5.15` for the Qwen3-Embedding work). A smaller DistilBERT-based ABSA candidate (`lhoestq/distilbert-base-uncased-finetuned-absa-as`) was found but not adopted, since its model card doesn't document whether it generalizes to arbitrary custom aspects (zero-shot, the property this whole pipeline depends on) or is locked to a fixed aspect set from its own training data, and confirming that would require real validation work, not just reading docs.

## Training

None. `yangheng/deberta-v3-base-absa-v1.1` is used off-the-shelf, zero-shot, no fine-tuning against Ludora's own data.

- Scripts, in order: `scripts/filter_eligible_reviews.py`, `scripts/absa_extract_hf.py`, `scripts/absa_aggregate.py`.
- Commands:
  ```bash
  uv run --project backend python scripts/filter_eligible_reviews.py
  uv run --project backend python scripts/absa_extract_hf.py
  uv run --project backend python scripts/absa_aggregate.py
  ```
  `absa_extract_hf.py` accepts `--game_id` (restrict to one game, for testing), `--limit` (cap reviews this run), and `--minutes` (stop after a wall-clock budget, `--minutes 30` for a bounded chunk, for instance); the full-corpus run is executed in repeated bounded sessions rather than one multi-hour sitting. Resume is tracked via `reviews.absa_processed_at`, set on every review the script runs inference on regardless of whether it produced any storable aspect rows; it processes in `quality_score` descending order, so an interrupted run leaves the best reviews done, not an arbitrary prefix. Each run prints a backlog summary (attempted, eligible, remaining, ETA at that session's rate).
- MLflow experiment: `reviews/absa` (run names `filter_eligible_reviews`, `extract`, `aggregate`), logging taxonomy size, thresholds, batch size, and, for extraction, total aspects extracted and elapsed time.
- A distinct, earlier pilot quality-filtering path (`scripts/absa_filter.py`, CSV-based over `master_reviews.csv`, not DB-based) logs under the same `reviews/absa` experiment (run name `pilot_filter`), kept as a separate run since it's a different, non-canonical, frozen path with its own inlined copy of the old quality-score formula, decoupled from `ABSAConfig`.

## Artifact

None trained or saved for the DeBERTa model itself (pretrained weights, downloaded from HuggingFace at runtime). `data/models/lid.176.ftz` (938 KB) is the pinned fastText language-ID model, a plain download, not a trained artifact. `data/review_quality_vocab_candidates.txt` and `data/boilerplate_ngrams.json` are corpus-statistics artifacts from `scripts/build_review_quality_vocab.py` (the former is a human-curation input, not consumed directly at runtime; the curated result lives in `ABSAConfig.DOMAIN_VOCABULARY`).

## Evaluation

**Status: does not exist for the classifier itself.** No ground-truth aspect-sentiment annotation set exists anywhere in this repo, so there's no automated way to check whether a given (review, aspect) sentiment prediction is correct. The DeBERTa model's own reported benchmark performance (from its model card on HuggingFace) is the only external signal available; nothing here validates it against Ludora's specific review corpus, and the model is trained on restaurant and laptop reviews, not board games, a real, disclosed domain-mismatch gap that the base-versus-large choice doesn't change either way.

What was checked: the quality filter's precision on real data, manually. Reading a sample of what the filter (before adding VADER) was passing surfaced genuine false positives, [BGG](https://boardgamegeek.com/) collection and trade-log notes and metadata dumps that scored well on density and diversity despite carrying zero opinion content (one numeric rating-breakdown scored the highest in a sample, 0.900, despite not being prose). Adding a VADER zero-sentiment check measurably improved this, removing about 22% of the previously-eligible pool, but it isn't a complete fix; see [Known limitations](#known-limitations).

## Known limitations

- **Eligibility is computed for the full corpus (267,950 reviews); classification is 39,484 reviews in (about 14.7%), run in resumable, time-boxed chunks rather than one sitting.** Measured throughput has held around 20-24 reviews per second across multiple chunked sessions spanning a range of games, giving a real remaining-time projection of roughly 3 to 3.5 hours across however many future chunks it takes.
- **The quality filter has a real, measured, disclosed precision ceiling.** VADER's zero-sentiment check catches most metadata and trade-log noise but misses cases where such text happens to contain a lexicon-positive word out of context ("3-6 Recommended 4-5 Best" describing player counts, not the game), and occasionally over-rejects genuine opinions with typos or uncommon sentiment words a fixed lexicon doesn't cover. That's an expected ceiling for a cheap, model-free filter, not a claim of perfect input quality.
- Neutral predictions are stored (with full probabilities), but not yet rolled into `game_aspect_aggregates` or shown in the UI.
- Evidence sentences are regex-matched, not model-selected, so they may not be the sentence that actually drove the sentiment classification.
- No accuracy evaluation exists for the classifier (see above); the domain mismatch between restaurant/laptop training data and board game reviews is unmeasured.
- `data/processed/pilot_absa_filtered.csv`, a leftover artifact from an earlier, removed Ollama-based approach, is still on disk. See `docs/ml/absa.md` for that history.
