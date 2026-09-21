# Ludora documentation

Start at [README.md](../README.md) for what this is and why. This page is the map.

These docs explain **why** things are built the way they are, and **how to run them**. They deliberately do not narrate what the code does. For that, read the code. Where a doc states a number, that number was measured, and the doc says how. Each one ends with its own **Known limitations**.

## The ML systems

| System | Problem | Doc |
|---|---|---|
| AI Assistant | Natural language over the catalog: typed parsing, deterministic execution | [ml/assistant.md](ml/assistant.md) |
| Search | Find a game by name, or by describing it | [ml/search.md](ml/search.md) |
| Review NLP | Per-aspect sentiment from 4.2M reviews, then a Community Consensus paragraph | [ml/absa.md](ml/absa.md) |
| Recommendations | Suggest related games, and let 9 algorithms be compared | [ml/recommenders.md](ml/recommenders.md) |

## The clients

- [../frontend/README.md](../frontend/README.md): the React web client, screen by screen
- [../ios/README.md](../ios/README.md): the native SwiftUI client, screen by screen

## How it works

- [architecture/README.md](architecture/README.md): service boundaries, request flow, the system diagram
- [architecture/data-pipeline.md](architecture/data-pipeline.md): which offline script runs when, and why in that order
- [data/README.md](data/README.md): dataset provenance, the BGG taxonomy, schema, data-quality rules, glossary

## Running and contributing

- [setup/README.md](setup/README.md): setup, environment variables, the local LLM server, and the security posture
- [engineering/testing.md](engineering/testing.md): the real state of test coverage
- [../AGENTS.md](../AGENTS.md): repo-wide conventions and invariants, plus nested files per side

Screenshots referenced throughout live in [assets/images/](assets/images/).
