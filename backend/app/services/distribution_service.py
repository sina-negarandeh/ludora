"""Serve the precomputed metric distributions.

`scripts/generate_distributions.py` reads the raw Kaggle CSV and writes kernel
density curves for a handful of metrics, per subdomain and overall. It is the
one pipeline artifact that never touched Postgres, so it used to sit in
`frontend/public/` and be fetched as a static file by the web app alone.

It lives next to the API now because a second client needs it. Three clients
reading one contract is the rule the rest of this API follows, and a copy
per client is the thing that drifts.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.schemas.distribution import MetricDistribution

logger = logging.getLogger(__name__)

DISTRIBUTIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "distributions.json"

_SCHEMA = TypeAdapter(dict[str, dict[str, MetricDistribution]])


class DistributionsUnavailableError(RuntimeError):
    """The artifact is missing, unreadable, or not the shape we serve."""


def read_distributions(source: Path) -> bytes:
    """Read and vet the artifact, returning the JSON bytes to serve.

    Bytes rather than a parsed dict, for two reasons. A cached dict would be
    handed to every caller by reference, so one in-place mutation anywhere
    would quietly change what every later request returns, with no file
    change to explain it. And the response is a fixed document: parsing it
    per request only to re-serialize the same thing is work with nothing to
    show for it.

    The shape is checked here rather than left to the route's
    `response_model`, which would validate the same unchanging payload on
    every request and, worse, silently drop any field the schema does not
    name. Validating once means artifact drift fails loudly on the first
    read instead of reaching a client as a quietly incomplete curve.

    `read_bytes` rather than `read_text`: `json.loads` decodes UTF-8 itself,
    so the read does not depend on whatever locale the process happens to
    have. An image defaulting to POSIX/ASCII would otherwise fail on the
    first accented group name.
    """
    try:
        raw = source.read_bytes()
    except FileNotFoundError as exc:
        raise DistributionsUnavailableError(
            f"{source} is missing. Run scripts/generate_distributions.py."
        ) from exc
    except OSError as exc:
        # Unreadable, a directory, a dead symlink. All of them mean the
        # artifact is broken rather than the API, same as a missing file.
        raise DistributionsUnavailableError(f"{source} could not be read: {exc}") from exc

    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DistributionsUnavailableError(f"{source} is not valid JSON: {exc}") from exc

    try:
        _SCHEMA.validate_python(payload)
    except ValidationError as exc:
        raise DistributionsUnavailableError(
            f"{source} does not match the distribution schema: {exc}"
        ) from exc

    return raw


@lru_cache(maxsize=1)
def load_distributions() -> bytes:
    """The artifact, read and vetted once.

    Takes no arguments on purpose. An injectable path would give one file
    several cache keys under `maxsize=1` and let a test evict the real entry;
    tests exercise `read_distributions` directly instead.
    """
    return read_distributions(DISTRIBUTIONS_PATH)
