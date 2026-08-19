# AI Assistant

**Status: Implemented for all 8 intents; stateless (no multi-turn memory) despite an accepted-but-unused `conversation_id` field.**

## Problem

Let a user express what they want in natural language ("economic games for 2-4 players") from a chat sidebar, instead of manually operating the filter sidebar.

## Inputs and outputs

Input: a free-text message (plus an accepted-but-ignored `conversation_id`; see [Known limitation](#known-limitation-no-multi-turn-memory) below). Output: a typed `AssistantResponse`, a `type` (`search_results` | `recommendations` | `clarification` | `game_detail` | `community_consensus` | `reviews` | `comparison` | `unsupported` | `error`) plus structured `data`, rendered by `AssistantMessageBubble` as inline cards, not free text.

## Approach: structured JSON parsing, not a semantic classifier

`AssistantService.parse_query()` (`backend/app/services/assistant_service.py`) sends the user's message to a local LLM (`Qwen/Qwen3-4B-MLX-4bit`) via the OpenAI Python SDK, with the full `ParsedIntent` Pydantic JSON schema embedded in the system prompt plus hand-written disambiguation examples ("strategy games" → `subdomains=["Strategy"]`). The prompt is prefixed with Qwen3's `/no_think` directive, since this is a "thinking"-capable model and unsuppressed reasoning output would land before the JSON and break parsing. `response_format={"type": "json_object"}`, temperature `0.0`. If `ParsedIntent.model_validate_json()` fails, the call retries up to `AssistantConfig.MAX_LLM_RETRIES` (2) times before raising, the same retry-on-empty-or-malformed-completion pattern `SummarizationService` uses.

This is deliberately not a semantic embedding classifier. Routing happens by asking the LLM to fill in a typed `intent` enum field, then dispatching on that string with a plain `if`/`elif` chain in `AssistantOrchestrator`. That's a reasonable, common pattern for structured LLM output, but it should be described as LLM-based structured intent extraction, not semantic routing or an intent classifier; those terms imply a trained classification model, which doesn't exist here. It's also a single-shot dispatcher, not an agent loop: one LLM call classifies the request, then a fixed handler runs for that intent. Nothing here plans across multiple steps, because none of the eight intents need more than one.

### `ParsedIntent` schema (`backend/app/schemas/assistant.py`)

```
intent: "browse" | "search" | "recommend" | "compare" | "get_game" | "get_reviews" | "get_aspects" | "unsupported"
needs_clarification: bool
clarification_question, query, game_name: optional strings
game_names: optional string list (compare only, 2+ titles)
requested_facts: optional list of "rank" | "rating" | "complexity" | "player_count" | "age" | "playtime" (get_game only)
search_mode: "lexical" | "semantic" | "hybrid"
filters: GameFilters   (themes, mechanics, categories, subdomains, families, designers, artists, publishers,
                        min/max players, exact players, min/max complexity, min/max year)
sort: SortSpec         (field, direction)
recommendation_family: "popularity" | "content" | "collaborative" | "hybrid"
recommendation_model, limit
```

## Orchestration

`AssistantOrchestrator.execute()` (`backend/app/services/assistant_orchestrator.py`) dispatches on `intent.intent`:

| Intent | Handler |
|---|---|
| `browse` | `GameService.get_games()` via `_map_filters` + `EntityResolver`; degrades to a text search if a filter value doesn't resolve against the real taxonomy |
| `search` | `SearchService.search()`; drops any filter value that doesn't resolve rather than failing the whole request |
| `recommend` | `RecommendationService.get_recommendations()`, model defaults to `hybrid` |
| `compare` | Resolves 2 to `MAX_COMPARE_GAMES` (5) named titles via `EntityResolver` and `GameService.get_game()`, renders a side-by-side comparison table |
| `get_game` | `GameService.get_game()`; if `requested_facts` is set, answers with a direct pointed statement instead of a full summary |
| `get_aspects` | `AspectService.get_game_aspects()` plus the game's `customer_summary`; returns the community consensus paragraph and per-aspect sentiment breakdown |
| `get_reviews` | `ReviewService.get_game_reviews()`; returns actual review text, distinct from `get_aspects`'s summary |
| `unsupported` | Returns a fixed, deterministically-worded decline; the message text isn't LLM-generated, since a small model can't be trusted to phrase a graceful redirect consistently |

If `needs_clarification` is set, or an `AmbiguousEntityError`/`EntityNotFoundError` is raised during entity resolution, the orchestrator returns a `clarification` response with up to 5 candidate matches instead of executing the intent.

## Entity resolution

`EntityResolver` (`backend/app/services/entity_resolver.py`) keeps class-level (shared across requests) lowercase-name caches for every tag type. It splits resolution into two paths: content tags (categories, subdomains, themes, mechanics, families) are cross-checked against every cache, since they're conceptually disjoint and this self-corrects an LLM field mis-assignment; credit tags (designers, artists, publishers) resolve only within their own field's cache, since a real person can legitimately hold multiple credited roles (Uwe Rosenberg exists as both a designer and an artist in the data, and cross-checking him against every cache produced a false ambiguity).

Game name resolution (`resolve_game()`) doesn't use a fuzzy-matching library (no `rapidfuzz`, no `difflib`); it delegates to `SearchService`'s lexical search mode, then applies simple logic on top: an exact case-insensitive match wins outright, exactly one lexical result is accepted as a match, and anything else raises `AmbiguousEntityError` (with candidates) or `EntityNotFoundError`. "Fuzzy" here really means "whatever Postgres full-text search considers a match," not a dedicated string-similarity algorithm.

## Known limitation: no multi-turn memory

`conversation_id` is declared in three places and used in none of them:

- `ParseRequest.conversation_id` (`backend/app/api/routes/assistant.py`): accepted, never read by either handler
- `ChatRequest.conversation_id` (`frontend/src/api/assistant.ts`): declared, never populated by any call site
- `AssistantDrawer.tsx`: the one call site only ever sends `{ message: text }`

Every `/api/assistant/chat` call is fully stateless. There's no rolling memory buffer, no session state, and no mechanism anywhere in the codebase for a follow-up query to reference an earlier turn.

## Failure modes and limitations

- `compare` needs two or more named titles. A franchise or series reference ("compare the Brass games") doesn't resolve to a concrete pair yet; the LLM either under-extracts to one name or invents a title that doesn't exist in the catalog.
- The assistant's filter set has no playtime fields, unlike the catalog's direct browse and search filters, so a request like "short games under 30 minutes" can't be expressed as a structured filter today.
- No conversation memory (above); every message is parsed with zero context from prior turns in the same session.
- No evaluation set of natural-language queries with expected parsed intents exists; parsing correctness is unverified beyond the hand-run queries in `backend/test_orchestrator.py` (a print-only script, no assertions, requires both a live DB and a live LLM server).

## Related code

- `backend/app/services/assistant_service.py`, `assistant_orchestrator.py`, `entity_resolver.py`
- `backend/app/schemas/assistant.py`
- `backend/app/api/routes/assistant.py`
- `backend/test_assistant.py`, `test_assistant_retry.py`, `test_orchestrator.py` (all print-only, no assertions; see [docs/engineering/testing.md](../engineering/testing.md))
- `frontend/src/components/AssistantDrawer.tsx`, `AssistantMessageBubble.tsx`, `CompactGameRow.tsx`
- `frontend/src/api/assistant.ts`
