# ios/AGENTS.md

Scope: `ios/`. Read [../AGENTS.md](../AGENTS.md) first.

Native iOS client for the same API the React frontend uses. It reads the catalog. It does not compute anything.

## Stack

Swift 6 (strict concurrency), SwiftUI, iOS 17 minimum. Swift Package Manager, no third-party dependencies. `URLSession` + `async/await` for networking, Swift Testing for tests, `@Observable` for state.

No Alamofire, no image library, no persistence layer. Each was considered and left out: the client makes seven kinds of request, `URLCache` already handles HTTP caching, and nothing here needs to survive a relaunch. Add one when a real problem calls for it, not preemptively.

## Layout

```
ios/
├── LudoraKit/          Swift package: models, API client, tests. No UI.
└── Ludora/             SwiftUI app. Views only, thin over LudoraKit.
```

The split is not ceremony. `LudoraKit` imports only Foundation, so it builds and tests with `swift test` on macOS. It needs no Xcode project, no simulator, and no booted device.

That is the same rule `backend/tests/` follows. A test that needs a booted simulator does not run in CI. A test that needs a running backend fails for reasons unrelated to the code.

Put logic in `LudoraKit`. If a piece of behavior is worth testing, it does not belong in a `View`.

## Commands

```bash
make ios-build       # swift build (the package)
make ios-test        # swift test (the package)
make ios-fixtures    # re-capture test fixtures from a running backend
make ios-typecheck   # typecheck the SwiftUI sources against the iOS SDK
```

Xcode builds and runs the app target itself, at `ios/Ludora/Ludora.xcodeproj`. See [README.md](README.md) for the two things about that project that are easy to undo by accident.

## Scope: what this client deliberately does not do

Browse, filter, sort, search, game detail with its stat distributions, rankings, ratings, and reviews. That is all of it.

Recommendations, the ABSA aspect breakdown, the LLM community-consensus paragraph, and the AI assistant all exist on the backend. They are intentionally absent here. `Game` does not even model `customer_summary`.

A model that carries fields the UI never renders invites someone to connect them by accident. The omission is therefore in the type, not just the views.

## Talking to the backend

The backend must be running (`make backend`) with Postgres up (`make up`). The simulator shares the host network, so `LudoraConfiguration.localhost` works there with no setup. A physical device cannot resolve the host's localhost and needs `LudoraConfiguration.lan(host:)` with the Mac's LAN address. The backend already runs with `allow_origins=["*"]`, so nothing changes server-side either way.

## Contract drift is the real risk

Three clients now read one API contract, and nothing type-checks Swift against Python. `LudoraKit/Tests/LudoraKitTests/Fixtures/` holds real captured responses, not hand-written JSON, and the decoding tests run against them. When the backend changes a shape, `make ios-fixtures` followed by `make ios-test` fails with the field named, instead of the app failing on screen.

Two rules that follow from this, both learned by mutation-testing these tests:

- **Decode strictly**. Do not write `decodeIfPresent(...) ?? []` for a field the API guarantees. It converts a genuine contract break into a silently empty list, which defeats the entire point. Verified over a 200-game sample: the tag vocabularies are always present, always arrays, sometimes empty, never null.
- **Follow the schema, not the data sample**. `rank`, `game_weight` and `year_published` were never null across 800 sampled games, but `GameResponse` declares them nullable. They stay optional here. An ingest that adds an unranked game must not crash the client.

## Conventions

- Models mirror the backend's Pydantic schemas, with `CodingKeys` doing the snake_case to camelCase mapping. Do not rename a concept on the way across.
- `LudoraError` writes the user-facing string. Views render `errorDescription`. They do not build error messages themselves.
- Filters apply on dismiss, not per-toggle. Every change is a network round trip.
