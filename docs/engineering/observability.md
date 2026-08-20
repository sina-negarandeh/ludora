# Observability

**Status: real, verified, end-to-end for the live API process only.** Structured logging (`structlog`), distributed tracing, metrics, and log export all run and were confirmed against actual exported data, not just "the code imports the SDK." The offline pipeline (`scripts/`) and the AI Assistant's LLM-specific tracing (Langfuse) are not instrumented -- see "What's not wired" below.

## What's wired

**`structlog`** (`backend/app/core/logging_config.py`): every HTTP request (method, path, status, duration) and every `AssistantService` LLM call (model, attempt, duration, outcome) is logged, console-rendered as `key=value` pairs for local reading.

**OpenTelemetry** (`backend/app/core/otel_config.py`), one OTLP/gRPC connection to a local collector, `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://localhost:4317`, `backend/app/core/config.py`):
- **Traces**: FastAPI (`FastAPIInstrumentor`, `app/main.py`), SQLAlchemy (`SQLAlchemyInstrumentor`, `app/database/session.py`), and httpx (`HTTPXClientInstrumentor`, backs the `openai` SDK calls in `assistant_service.py`/`summarization_service.py`) are all auto-instrumented. A single request produces one HTTP server span with real nested child spans for every DB query and every outbound HTTP call it makes.
- **Metrics**: the FastAPI instrumentor emits request duration/count/response-size histograms automatically; no custom metrics written yet.
- **Logs**: `logging_config.py`'s structlog pipeline tees every event to a dedicated, non-propagating stdlib logger (`ludora.otel_export`) that an OTel `LoggingHandler` forwards as an OTLP log record, in addition to (not instead of) the normal console render. The same processor also injects the current span's `trace_id`/`span_id` into the event dict, so both the console line and the shipped log carry it, in the same `key=value` text.

**The collector and backends** (`observability/`, opt-in via `make observability-up`, see `observability/README.md`): one OTel Collector receives all three signals and fans them out -- traces to Tempo, logs to Loki (native OTLP ingestion), metrics to its own `:8889` for Prometheus to scrape. Grafana's three datasources are auto-provisioned with trace↔log↔metric correlation wired in (`Tempo.tracesToLogsV2` keyed on the same `trace_id=` text the Loki log line contains).

Degrades the same way the local LLM server does (`backend/AGENTS.md`): if the collector isn't running, OTLP exports fail/retry in the background and every endpoint keeps working exactly as before. Nothing here is required to run the app.

## What's not wired

- **Langfuse / LLM-specific tracing.** The assistant's own two OTel-free things -- prompt/completion content, token counts, model-quality signal -- aren't captured anywhere. `AssistantService`'s structlog lines record duration and pass/fail per attempt, nothing about the prompt or response itself.
- **The offline pipeline** (`scripts/`, `backend/evaluation/`) emits no telemetry at all. Only the live `uvicorn` process is instrumented; a script run is invisible to this stack.
- **No Grafana dashboards.** The `observability/grafana/provisioning/dashboards/` directory exists (so Grafana's provisioner doesn't error on startup) but is empty -- Explore-view queries only, no saved dashboard.
- **No alerting, no retention policy, no auth on Grafana** (anonymous admin login) -- a local-dev/demo posture, consistent with this project's no-auth stance elsewhere (`AGENTS.md` boundaries), not a production configuration.

## Evidence

Verified directly against a running stack (`make observability-up` + `uv run uvicorn app.main:app`), not assumed from the code alone:

- `GET /api/games/?limit=3` produced a trace queryable at `GET http://localhost:3200/api/traces/<trace_id>` containing one `SPAN_KIND_SERVER` span (`GET /api/games/`) with 9 nested `SPAN_KIND_CLIENT` `SELECT ludoradb` spans (the real queries `GameService` issues for that endpoint) plus a `connect` span, all tagged `service.name=ludora-backend`.
- `GET http://localhost:9090/api/v1/query?query=http_server_duration_milliseconds_count` returned a real vector result labeled `exported_job="ludora-backend"`, confirming metrics reach Prometheus through the collector's scrape endpoint.
- `GET http://localhost:3100/loki/api/v1/query_range?query={service_name="ludora-backend"}` returned log lines carrying the identical `trace_id`/`span_id` as the corresponding Tempo trace, rendered as `method=GET path=/api/games/ status_code=200 duration_ms=381.4 ... trace_id=143ec... span_id=9b70...` -- the same text the console shows, confirming the Grafana Loki datasource's `derivedFields` regex (`trace_id=(\w+)`) will actually match real log lines, not just the config's intent.

## Run it

```bash
make observability-up   # collector + prometheus + loki + tempo + grafana
cd backend && uv run uvicorn app.main:app --reload
```

Grafana: http://localhost:3000 (Explore, pick a datasource). Full port/URL table and data-flow diagram: `observability/README.md`.

## Known limitations

- **Opt-in only**, not part of `make up` -- five extra containers with nothing to show until the backend actually runs, and no reason to pay that startup cost for routine dev work unrelated to observability.
- **A few seconds of lag** between a request and its data appearing in Grafana -- both the span and metric exporters batch/flush periodically (SDK defaults), not real-time streaming.
- **Local-dev config only**: filesystem storage, no replication, no retention policy (`observability/*.yaml`, each says so directly). Not tuned for, or evidence of, production-scale operation.

## Related code

- `backend/app/core/logging_config.py`, `backend/app/core/otel_config.py`, `backend/app/core/config.py` (`OTEL_EXPORTER_OTLP_ENDPOINT`)
- `backend/app/main.py` (`FastAPIInstrumentor`), `backend/app/database/session.py` (`SQLAlchemyInstrumentor`)
- `observability/` (`README.md`, `otel-collector-config.yaml`, `prometheus.yml`, `loki-config.yaml`, `tempo.yaml`, `grafana/provisioning/`)
- `docker-compose.yml` (`observability` profile), `Makefile` (`observability-up`/`-down`/`-logs`)
