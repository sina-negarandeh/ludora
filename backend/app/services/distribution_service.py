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
from typing import Any

logger = logging.getLogger(__name__)

DISTRIBUTIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "distributions.json"


class DistributionsUnavailableError(RuntimeError):
    """The artifact is missing or unreadable."""


@lru_cache(maxsize=1)
def load_distributions(path: str | None = None) -> dict[str, Any]:
    """Read the artifact once and hold it.

    It is a fixed ~28KB of numbers that only changes when the pipeline reruns,
    so re-reading it per request would be pure waste. The cache is keyed on the
    path so a test can point at a fixture without poisoning the real entry.
    """
    source = Path(path) if path else DISTRIBUTIONS_PATH
    try:
        return json.loads(source.read_text())
    except FileNotFoundError as exc:
        raise DistributionsUnavailableError(
            f"{source} is missing. Run scripts/generate_distributions.py."
        ) from exc
    except json.JSONDecodeError as exc:
        raise DistributionsUnavailableError(f"{source} is not valid JSON: {exc}") from exc
