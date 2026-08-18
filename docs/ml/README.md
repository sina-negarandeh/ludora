# ML / AI systems

Ludora has four distinct ML/AI systems, documented separately because they solve different problems with different techniques. Each doc uses the same status vocabulary: **Implemented** (code exists and runs), **Tested** (exercised by some form of automated check — rare in this repo, see [docs/engineering/testing.md](../engineering/testing.md)), **Measured** (a real, committed result exists), **Observed** (a plausible output exists but isn't traceable to a committed artifact), **Designed** (specified but not built), **Planned** (mentioned as future work), **Known Limitation** (built, but with a disclosed gap).

| System | Problem | Doc |
|---|---|---|
| Search | Find games by keyword or natural-language description | [search.md](search.md) |
| Recommendation engine | Suggest similar/related games; compare 9 algorithms side by side | [recommenders.md](recommenders.md) |
| ABSA + summarization | Extract per-aspect sentiment from reviews; synthesize a "Community Consensus" paragraph | [absa.md](absa.md) |
| AI Assistant | Natural-language chat interface over the catalog | [assistant.md](assistant.md) |

Measured/observed results for all four systems (what's real, what's UI-only, what's missing) are consolidated in [evaluation.md](evaluation.md). The exact reproducibility spec for each individual model — data, hyperparameters, training command, artifact location, evaluation result — is in [model-cards/](model-cards/), one file per model.

## The offline/online split, in one sentence

With the exception of live search and 3 of the 9 recommendation model IDs (`popularity`, `embedding`, `hybrid`), everything above is populated by an offline Python script writing to Postgres — the FastAPI layer mostly reads, it rarely computes. See [docs/architecture/README.md](../architecture/README.md) for the system diagram and [docs/architecture/data-pipeline.md](../architecture/data-pipeline.md) for the exact script order.

## What's genuinely distinctive here

- **Hybrid search via Reciprocal Rank Fusion** (`k=60`) combining Postgres full-text search and pgvector semantic search in one request-time code path.
- **Two real collaborative-filtering implementations** (Item-Item Cosine using adjusted, mean-centered similarity per Sarwar et al. 2001; ALS using Hu/Koren/Volinsky 2008 confidence weighting) following a consistent `BaseRecommender` ABC — the only part of the recommendation engine built as reusable classes rather than one-off scripts.
- **A 17-aspect zero-shot ABSA classifier** (`yangheng/deberta-v3-base-absa-v1.1`) with a cheap, model-free quality/eligibility filter (`app.core.review_quality` — language reuse, hard filters including a VADER sentiment check, SimHash dedup, a weighted density/diversity/specificity/boilerplate score) that runs over the full ~4.2M-review corpus rather than a pre-restricted sample — a real NLP pipeline, evidenced by two superseded implementation attempts visible in git history (see [absa.md](absa.md)).
- **Structured LLM output** (JSON-schema-constrained, Pydantic-validated) used for two different jobs — intent parsing and review summarization — against a local, OpenAI-compatible MLX server, with no cloud LLM dependency.

## What's honestly missing

- No persisted evaluation results for any of the four systems ([evaluation.md](evaluation.md)).
- ABSA classification is running in resumable chunks and has attempted 39,484 of 267,950 eligible reviews so far (~14.7%), not the full corpus yet ([absa.md](absa.md#coverage-full-corpus-filtered-not-sampled)).
- The AI Assistant has no multi-turn memory despite an accepted `conversation_id` field ([assistant.md](assistant.md#known-limitation-no-multi-turn-memory)).

Full list, including engineering and data gaps: [docs/limitations.md](../limitations.md).
