import time

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.api.routes import assistant, games, metadata, recommendations, search
from app.core.logging_config import configure_logging
from app.core.otel_config import configure_otel

# Order between these two doesn't matter: both just register global state
# (structlog's processor chain, OTel's providers/handler) -- nothing
# actually logs until a request comes in, well after both have run.
configure_logging()
configure_otel()
logger = structlog.get_logger("ludora.request")

app = FastAPI(title="Ludora API", version="0.1.0")
FastAPIInstrumentor.instrument_app(app)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Deliberately outside any try/except: an unhandled exception here
    # should propagate exactly as it would without this middleware, not
    # get silently swallowed by a logging concern.
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response

app.include_router(games.router, prefix="/api/games", tags=["games"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(metadata.router, prefix="/api", tags=["metadata"])
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["assistant"])
@app.get("/health")
def health_check():
    return {"status": "ok"}
