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

from app.api.routes import metadata
from app.main import app
from app.services.distribution_service import (
    DISTRIBUTIONS_PATH,
    DistributionsUnavailableError,
    load_distributions,
    read_distributions,
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
    with pytest.raises(DistributionsUnavailableError, match="generate_distributions"):
        read_distributions(tmp_path / "nope.json")


def test_reports_a_corrupt_artifact_rather_than_crashing(tmp_path):
    corrupt = tmp_path / "distributions.json"
    corrupt.write_text("{not json")
    with pytest.raises(DistributionsUnavailableError, match="not valid JSON"):
        read_distributions(corrupt)


def test_reports_an_unreadable_artifact_rather_than_crashing(tmp_path):
    """A directory, a permissions problem: still the artifact, not the API."""
    with pytest.raises(DistributionsUnavailableError, match="could not be read"):
        read_distributions(tmp_path)


def test_rejects_an_artifact_that_does_not_match_the_schema(tmp_path):
    """Drift fails on read rather than reaching a client as a partial curve.

    `response_model` alone would not catch this: pydantic drops unknown keys
    and would happily serve a curve missing `cdf` as one that simply has no
    cdf.
    """
    wrong = tmp_path / "distributions.json"
    wrong.write_text(json.dumps({"Overall": {"Complexity": {"x": [1.0], "density": [1.0]}}}))
    with pytest.raises(DistributionsUnavailableError, match="does not match"):
        read_distributions(wrong)


def test_decodes_utf8_regardless_of_locale(tmp_path):
    """Read as bytes, so an ASCII-defaulting locale cannot break a group name."""
    source = tmp_path / "distributions.json"
    curve = {"x": [1.0], "density": [1.0], "cdf": [1.0], "min": 1.0, "max": 2.0}
    source.write_bytes(
        json.dumps({"Ameritrash\u00e9": {"Complexity": curve}}, ensure_ascii=False).encode()
    )
    assert "Ameritrash\u00e9".encode() in read_distributions(source)


def test_reads_the_file_once():
    """The artifact is fixed between pipeline runs, so it is cached."""
    load_distributions.cache_clear()
    load_distributions()
    load_distributions()
    info = load_distributions.cache_info()
    assert (info.hits, info.misses) == (1, 1), info


def test_serves_503_when_the_artifact_is_unavailable(client: TestClient, monkeypatch):
    """The route has to turn the service's error into a 503, not a 500."""
    def unavailable() -> bytes:
        raise DistributionsUnavailableError("distributions.json is missing.")

    monkeypatch.setattr(metadata, "load_distributions", unavailable)
    response = client.get("/api/distributions")
    assert response.status_code == 503
    assert "missing" in response.json()["detail"]
