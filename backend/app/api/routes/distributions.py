from fastapi import APIRouter, HTTPException, Response

from app.schemas.distribution import MetricDistribution
from app.services.distribution_service import (
    DistributionsUnavailableError,
    load_distributions,
)

router = APIRouter(tags=["distributions"])


@router.get("/distributions", response_model=dict[str, dict[str, MetricDistribution]], summary="Get Metric Distributions", description="Retrieve precomputed kernel density curves for Complexity, Playtime, Players, Min Players and Min Age, keyed by subdomain plus an 'Overall' group. Produced offline by scripts/generate_distributions.py from the raw Kaggle CSV, so this reads a static artifact rather than the database.")
def get_distributions():
    """Its own module rather than a ninth route in `metadata.py`.

    Everything there is a one-line `MetadataService(db).get_x(...)` over the
    database. This takes no session, reads a file, and hands back bytes, so
    sitting among them cost that module its single shape and made five of its
    imports exist for one outlier.

    `response_model` is the published OpenAPI schema, not a runtime check:
    returning a `Response` bypasses it by design. Enforcement happens once in
    `read_distributions`, against the same model, and covers more than
    `response_model` would -- it validates the curve is actually drawable,
    where `response_model` silently drops fields it does not recognise.
    """
    try:
        return Response(content=load_distributions(), media_type="application/json")
    except DistributionsUnavailableError as exc:
        # A 503 rather than a 500: the API is fine, the offline artifact is
        # not, and the fix is to run the pipeline rather than to debug this.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
