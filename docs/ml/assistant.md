# AI Assistant

**Status: Implemented for 5 of 7 intents; stateless (no multi-turn memory) despite an accepted-but-unused `conversation_id` field.**

## Problem

Let a user express what they want in natural language ("economic games for 2-4 players") from a chat sidebar, instead of manually operating the filter sidebar.

## Inputs and outputs

Input: a free-text message (plus an accepted-but-ignored `conversation_id` — see [Known limitation](#known-limitation-no-multi-turn-memory) below). Output: a typed `AssistantResponse` — a `responseType` (`search_results` | `comparison` | `recommendations` | `clarification` | `game_detail`) plus structured `data`, rendered by `AssistantMessageBubble` as inline cards, not free text.

## Approach: structured JSON parsing, not a semantic classifier

`AssistantService.parse_query()` (`backend/app/services/assistant_service.py`) sends the user's message to a local LLM via the OpenAI Python SDK, with the full `ParsedIntent` Pydantic JSON schema embedded in the system prompt plus hand-written disambiguation examples (e.g. `"strategy games" -> categories=["Strategy"]`). One call, `response_format={"type": "json_object"}`, temperature `0.0`; the raw response is validated with `ParsedIntent.model_validate_json()`. **There is no retry logic** — a validation failure raises straight to the caller. (`backend/test_assistant_retry.py`, despite its name, only polls for the local LLM server to finish booting — it does not retry a failed parse.)

This is deliberately *not* a semantic embedding classifier — routing happens by asking the LLM to fill in a typed `intent` enum field, then dispatching on that string with a plain `if`/`elif` chain in `AssistantOrchestrator`. That's a reasonable, common pattern for structured LLM output, but it should be described as "LLM-based structured intent extraction," not "semantic routing" or "an intent-classifier" — those terms imply a trained classification model, which doesn't exist here.

### `ParsedIntent` schema (`backend/app/schemas/assistant.py`)

```
intent: "browse" | "search" | "compare" | "recommend" | "get_game" | "get_reviews" | "get_aspects"
needs_clarification: bool
clarification_question, query, game_name, game_names: optional strings
search_mode: "lexical" | "semantic" | "hybrid"
filters: GameFilters   (themes, mechanics, categories, min/max players, complexity, year)
sort: SortSpec         (field, direction)
recommendation_family: "content" | "collaborative" | "hybrid"
recommendation_model, limit
```

## Orchestration

`AssistantOrchestrator.execute()` (`backend/app/services/assistant_orchestrator.py`) dispatches on `intent.intent`:

| Intent | Status | Handler |
|---|---|---|
| `browse` | Implemented | `GameService.get_games()` via `_map_filters` + `EntityResolver` |
| `search` | Implemented | `SearchService.search()` |
| `compare` | Implemented | `GameService.compare_games()`, requires ≥2 resolved games |
| `recommend` | Implemented | `RecommendationService.get_recommendations()`, model defaults to `hybrid` |
| `get_game` | Implemented | `GameService.get_game()` |
| `get_reviews` | **Stub** | Falls back to `_handle_get_game()` |
| `get_aspects` | **Stub** | Falls back to `_handle_get_game()` |

The stub behavior is an explicit, quoted comment in the source, not an inference:

```python
elif intent.intent in ["get_reviews", "get_aspects"]:
    # Not fully implemented in services yet, but we map it
    return self._handle_get_game(intent) # fallback for now
```
— `backend/app/services/assistant_orchestrator.py:40-42`

If `needs_clarification` is set, or an `AmbiguousEntityError`/`EntityNotFoundError` is raised during entity resolution, the orchestrator returns a `clarification` response with up to 5 candidate matches instead of executing the intent.

## Entity resolution

`EntityResolver` (`backend/app/services/entity_resolver.py`) keeps class-level (shared across requests) lowercase-name caches for categories/themes/mechanics, loaded once. Game name resolution (`resolve_game()`) does **not** use a fuzzy-matching library (no `rapidfuzz`, no `difflib`) — it delegates to `SearchService`'s lexical search mode, then applies simple logic on top: an exact case-insensitive match wins outright; exactly one lexical result is accepted as a match; anything else raises `AmbiguousEntityError` (with candidates) or `EntityNotFoundError`. "Fuzzy" here really means "whatever Postgres full-text search considers a match," not a dedicated string-similarity algorithm.

## Known limitation: no multi-turn memory

`conversation_id` is declared in three places and used in none of them:

- `ParseRequest.conversation_id` (`backend/app/api/routes/assistant.py`) — accepted, never read by either handler
- `ChatRequest.conversation_id` (`frontend/src/api/assistant.ts`) — declared, never populated by any call site
- `AssistantDrawer.tsx:44` — `// In the future, pass conversation_id here`, directly above the one call site that only ever sends `{ message: text }`

Every `/api/assistant/chat` call is fully stateless. There is no rolling memory buffer, no session state, and no mechanism anywhere in the codebase for a follow-up query to reference an earlier turn. This directly contradicts a "Contextual Memory" claim in the pre-Phase-2 README, which the rewritten README removes.

## Failure modes and limitations

- No retry on a malformed/invalid LLM JSON response — the request fails outright.
- No conversation memory (above) — every message is parsed with zero context from prior turns in the same session.
- `get_reviews`/`get_aspects` intents exist in the schema and can be selected by the LLM, but silently degrade to a generic game-detail response rather than erroring or being visibly unavailable.
- No evaluation set of natural-language queries with expected parsed intents exists — parsing correctness is unverified beyond the three example queries in `backend/test_orchestrator.py` (a print-only script, no assertions, requires both a live DB and a live LLM server).

## Related code

- `backend/app/services/assistant_service.py`, `assistant_orchestrator.py`, `entity_resolver.py`
- `backend/app/schemas/assistant.py`
- `backend/app/api/routes/assistant.py`
- `backend/test_assistant.py`, `test_assistant_retry.py`, `test_orchestrator.py` (all print-only, no assertions — see [docs/engineering/testing.md](../engineering/testing.md))
- `frontend/src/components/AssistantDrawer.tsx`, `AssistantMessageBubble.tsx`, `CompactGameRow.tsx`
- `frontend/src/api/assistant.ts`
