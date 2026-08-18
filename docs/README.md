# Ludora documentation

Start with [README.md](../README.md) for the 60-second overview, or [case-study.md](case-study.md) for the full narrative. This index groups everything else by reader intent.

## I want the full story
- [case-study.md](case-study.md) — problem → product → architecture → data → ML → results → tradeoffs

## I want to see what it does
- [product/features.md](product/features.md) — every feature, with real screenshots, evidence, and known limitations

## I want to understand how it's built
- [architecture/README.md](architecture/README.md) — system design, service boundaries, request flows, diagram
- [architecture/data-pipeline.md](architecture/data-pipeline.md) — the offline ETL/ML script order, script by script
- [data/README.md](data/README.md) — dataset provenance, schema, taxonomy, data quality rules, glossary

## I want the ML/AI detail
- [ml/README.md](ml/README.md) — overview and index of all four systems
- [ml/search.md](ml/search.md) — lexical, semantic, hybrid (RRF) search
- [ml/recommenders.md](ml/recommenders.md) — the 10-model recommendation engine, including a disclosed serving bug
- [ml/absa.md](ml/absa.md) — aspect-based sentiment analysis + LLM summarization
- [ml/assistant.md](ml/assistant.md) — the conversational AI assistant
- [ml/evaluation.md](ml/evaluation.md) — measured vs. observed vs. unevaluated, system by system

## I want to run it or contribute
- [setup/README.md](setup/README.md) — verified setup, environment variables, local LLM server
- [engineering/testing.md](engineering/testing.md) — the actual state of test coverage
- [../AGENTS.md](../AGENTS.md) — navigation and invariants for anyone extending this repo

## I want the unvarnished truth
- [limitations.md](limitations.md) — every known gap, in one place
- [roadmap.md](roadmap.md) — concretely evidenced planned/unfinished work
- [audit/phase-1-audit.md](audit/phase-1-audit.md) — the repository audit this documentation set was built from

## I'm updating these docs after a code change
- [maintenance/coverage-map.md](maintenance/coverage-map.md) — which docs claim what, so a change propagates everywhere it needs to, not just to the first doc you find

## Assets
- [assets/images/](assets/images/) — screenshots referenced throughout this documentation set
