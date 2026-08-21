# Observability stack

The LGTM pattern (Loki, Grafana, Tempo, Prometheus) plus an OpenTelemetry
Collector as the single ingestion point. Opt-in, not part of `make up` --
see the rationale in `docker-compose.yml`'s `observability` profile
comment.

## Status

**Real, verified, end-to-end.** The backend (`backend/app/core/otel_config.py`)
instruments FastAPI, SQLAlchemy, and httpx, and ships traces, metrics,
and structlog-sourced logs over one OTLP connection to the collector
here. Confirmed against actual exported data -- a live request produces
a real Tempo trace with nested DB spans, a matching Prometheus metric,
and a Loki log line carrying the same `trace_id`. Full detail and
evidence: `docs/engineering/observability.md`.

## Run it

```bash
make observability-up      # or: docker compose --profile observability up -d
```

| Service | URL | Purpose |
|---|---|---|
| Grafana | http://localhost:3000 | dashboards (Prometheus + Loki + Tempo datasources auto-provisioned, anonymous admin login, no-auth like the rest of this project) |
| Prometheus | http://localhost:9090 | metrics, scraped from the collector's `:8889` exporter |
| Loki | http://localhost:3100 | logs, ingested via OTLP |
| Tempo | http://localhost:3200 | traces, ingested via OTLP |
| OTel Collector | localhost:4317 (gRPC) / :4318 (HTTP) | what the backend (running natively on the host) sends OTLP to |

```bash
make observability-down    # stop and remove containers, keeps volumes
```

## How data flows

```
backend (native, on host) --OTLP--> otel-collector --> tempo    (traces)
                                                    --> loki     (logs, native OTLP ingestion)
                                                    --> :8889/metrics  <-- scraped by prometheus
grafana reads from prometheus + loki + tempo, with trace<->log<->metric
correlation wired in datasources.yaml (Tempo's tracesToLogsV2/tracesToMetrics,
Loki's derivedFields trace_id regex).
```

The backend never talks to Tempo/Loki/Prometheus directly -- one OTLP
stream to the collector, fanned out from there. See
`otel-collector-config.yaml` for the actual pipeline config.

## Configs

- `otel-collector-config.yaml` -- receivers, processors, and the three export pipelines
- `prometheus.yml` -- scrape target (the collector's `:8889`, not the app directly)
- `loki-config.yaml` -- single-binary, filesystem storage
- `tempo.yaml` -- OTLP receiver, local disk trace storage
- `grafana/provisioning/datasources/datasources.yaml` -- the three datasources + correlation wiring

All four are minimal, local-dev configs: no retention policy, no
replication, no object storage backend. Not tuned for production scale --
this is a demo/portfolio stack, not one serving real traffic.
