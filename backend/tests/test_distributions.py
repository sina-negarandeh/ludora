"""The precomputed metric distributions, and the endpoint serving them.

These curves used to be a static file under `frontend/public/`, fetched off
the web app's own origin. A second client needs them now, so they moved next
to the API. That move is the thing worth testing: the artifact has to be
where the service looks for it, and it has to still parse.

Nothing here needs Postgres or MLX. The endpoint reads a file, so it is
testable the way the rest of `backend/tests/` is.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.distribution_service import (
    DISTRIBUTIONS_PATH,
    DistributionsUnavailableError,
    load_distributions,
)

METRICS = {"Complexity", "Playtime", "Players", "Min Players", "Min Age"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_artifact_ships_with_the_backend():
    """The move is only real if the file is where the service looks."""
    assert DISTRIBUTIONS_PATH.exists(), (
        f"{DISTRIBUTIONS_PATH} is missing. It is produced by "
        "scripts/generate_distributions.py and committed."
    )


def test_endpoint_returns_every_group_and_metric(client: TestClient):
    response = client.get("/api/distributions")
    assert response.status_code == 200

    body = response.json()
    assert "Overall" in body, "the ungrouped baseline curve is what a client falls back to"
    for group, metrics in body.items():
        assert METRICS <= set(metrics), f"{group} is missing {METRICS - set(metrics)}"


def test_curves_are_internally_consistent(client: TestClient):
    """x, density and cdf are read positionally by every client drawing them.

    A ragged curve would not raise anywhere; it would silently draw a line
    that stops early.
    """
    body = client.get("/api/distributions").json()
    for group, metrics in body.items():
        for name, curve in metrics.items():
            where = f"{group}/{name}"
            assert len(curve["x"]) == len(curve["density"]) == len(curve["cdf"]), where
            assert curve["x"], f"{where} is empty"
            assert curve["min"] < curve["max"], where
            assert curve["x"] == sorted(curve["x"]), f"{where} bins are unordered"
            # A cumulative distribution that does not reach 1 means a client
            # placing a game on it reads a percentile that is quietly wrong.
            assert curve["cdf"] == sorted(curve["cdf"]), f"{where} cdf is not monotonic"
            assert curve["cdf"][-1] == pytest.approx(1.0, abs=1e-6), where


def test_reports_a_missing_artifact_rather_than_crashing(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(DistributionsUnavailableError, match="generate_distributions"):
        load_distributions(str(missing))


def test_reports_a_corrupt_artifact_rather_than_crashing(tmp_path):
    corrupt = tmp_path / "distributions.json"
    corrupt.write_text("{not json")
    with pytest.raises(DistributionsUnavailableError, match="not valid JSON"):
        load_distributions(str(corrupt))


def test_reads_the_file_once(tmp_path):
    """The artifact is fixed between pipeline runs, so it is cached.

    Deleting the file after a successful read must not break a later call:
    that is what proves the cache is real rather than incidental.
    """
    source = tmp_path / "distributions.json"
    source.write_text(json.dumps({"Overall": {}}))

    first = load_distributions(str(source))
    source.unlink()
    assert load_distributions(str(source)) is first
