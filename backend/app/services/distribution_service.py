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
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.schemas.distribution import MetricDistribution

DISTRIBUTIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "distributions.json"

_SCHEMA = TypeAdapter(dict[str, dict[str, MetricDistribution]])


class DistributionsUnavailableError(RuntimeError):
    """The artifact is missing, unreadable, or not the shape we serve."""


def read_distributions(source: Path) -> bytes:
    """Read and vet the artifact, returning the JSON bytes to serve.

    Bytes, not a parsed dict: the result is cached, and a cached dict would be
    handed to every caller by reference, one mutation away from changing every
    later response.

    Raises `DistributionsUnavailableError` for anything wrong with the file,
    naming which step failed.
    """
    try:
        raw = source.read_bytes()
        # `json.loads` decodes UTF-8 itself, so reading bytes keeps this
        # independent of whatever locale the process happens to have.
        _SCHEMA.validate_python(json.loads(raw))
    except FileNotFoundError as exc:
        raise DistributionsUnavailableError(
            f"{source} is missing. Run scripts/generate_distributions.py."
        ) from exc
    except OSError as exc:
        # Unreadable, a directory, a dead symlink: the artifact is broken
        # rather than the API, same as a missing file.
        raise DistributionsUnavailableError(f"{source} could not be read: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DistributionsUnavailableError(f"{source} is not valid JSON: {exc}") from exc
    except ValidationError as exc:
        raise DistributionsUnavailableError(
            f"{source} does not match the distribution schema: {exc}"
        ) from exc

    return raw


@lru_cache(maxsize=1)
def load_distributions() -> bytes:
    """The artifact, read and vetted once.

    Takes no arguments on purpose. An injectable path would give one file
    several cache keys under `maxsize=1` and let a test evict the real entry.
    Tests exercise `read_distributions` directly instead.
    """
    return read_distributions(DISTRIBUTIONS_PATH)
