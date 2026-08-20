# Langfuse (LLM tracing)

Self-hosted Langfuse v4, for `AssistantService`'s prompts/completions/token
usage -- separate from the LGTM stack (`observability/`), which traces
HTTP/DB/generic infra, not LLM content. Opt-in via its own compose profile.

## Status

**Real, verified.** `AssistantService` (`backend/app/services/assistant_service.py`)
imports `from langfuse.openai import OpenAI` -- Langfuse's drop-in
OpenAI client -- instead of the plain SDK, so both `parse_query()` and
`parse_plan()`'s `chat.completions.create()` calls are traced with zero
other code change. Verified against a real call: `POST
/api/assistant/parse` with `{"message": "tell me about brass
birmingham"}` produced a Langfuse trace (same `trace_id` as the
request's own OTel span) showing the full system prompt, the user
message, the parsed structured output, real token usage (5,978 prompt →
25 completion), latency (13.1s), and model params (`Qwen/Qwen3-4B-MLX-4bit`,
`temperature: 0`) -- confirmed in the UI, not just "the SDK call didn't
throw."

Composes cleanly with the LGTM stack's own OTel setup rather than
conflicting with it: Langfuse's SDK checks whether a real
`TracerProvider` is already registered (`app.core.otel_config`'s is,
since `configure_otel()` runs at app startup, before any request
constructs an `AssistantService`) and if so reuses it, adding its own
span processor rather than replacing the provider -- confirmed directly
by reading `langfuse/_client/resource_manager.py`. Its processor only
ever exports spans it recognizes as its own (`is_langfuse_span()`), so
the HTTP/DB spans our own OTel setup creates never get sent to
Langfuse, and Langfuse's LLM spans never get sent to Tempo.

## Why six containers

Langfuse v4's self-host stack is genuinely this size: Postgres (app
data), ClickHouse (trace/observation analytics store), Redis (queues),
minio (S3-compatible blob storage for events/media), plus the web app
and a background worker. This is Langfuse's own architecture, not
something this project chose to make heavier -- see the reference
`docker-compose.yml` at https://github.com/langfuse/langfuse.

## Run it

```bash
cp .env.example .env   # if you haven't already -- fill in real secrets, see the file's own comments
make langfuse-up       # or: docker compose --profile langfuse up -d
```

First boot takes longer than the LGTM stack (Postgres migrations +
ClickHouse schema setup inside langfuse-web/worker) -- give it 30-60s
before hitting the UI.

| Service | URL | Purpose |
|---|---|---|
| Langfuse web UI | http://localhost:3001 | traces, sessions, prompt/completion inspection -- login with `LANGFUSE_INIT_USER_EMAIL`/`LANGFUSE_INIT_USER_PASSWORD` from `.env` |
| Langfuse worker | localhost:3030 | background ingestion, no UI |
| ClickHouse | localhost:8123 (HTTP), :9000 (native) | trace storage, loopback-only |
| minio | localhost:9190 (S3 API), :9191 (console) | blob storage for events/media |
| Redis | localhost:6379 | queues, loopback-only |
| Langfuse's own Postgres | localhost:5433 | app data -- a separate instance from `ludora_db`, not shared |

Ports are remapped from Langfuse's own upstream defaults where they'd
collide with the observability stack: `langfuse-web` 3000->3001
(grafana owns 3000), minio 9090->9190 (prometheus owns 9090), and this
stack's own Postgres 5432->5433 (`ludora_db` owns 5432).

```bash
make langfuse-down     # stop and remove containers, keeps volumes
```

## Getting the backend an API key

`LANGFUSE_INIT_*` env vars (`.env`) auto-create a project and an
API keypair on first boot -- no manual "sign up, create a project, copy
a key" step. Copy `LANGFUSE_INIT_PROJECT_PUBLIC_KEY`/
`LANGFUSE_INIT_PROJECT_SECRET_KEY` from `.env` into `backend/.env` as
`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` (see `backend/.env.example`).

## Known limitations

- **Opt-in, separate profile from `observability`** -- six more
  containers with a real first-boot cost (ClickHouse schema setup);
  don't bring this up unless you're actually working on assistant
  tracing.
- **Local-dev secrets only.** `.env` holds real generated values but
  they're dev-only credentials for containers bound to localhost, not
  production secrets.
- **`AssistantService` only.** `SummarizationService` (the offline
  `scripts/generate_summaries.py` batch job) still uses the plain
  `openai.OpenAI` client -- out of scope here since it's not "the AI
  Assistant," and it's an offline job the LGTM stack doesn't cover
  either.
- **Degrades silently without credentials**, same posture as every
  other optional-infra setting in this app: if `backend/.env` has no
  `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY`, the Langfuse SDK logs one warning
  and falls back to a no-op tracer -- the assistant keeps working
  exactly as before, just untraced.
