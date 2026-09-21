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

from app.api.routes import distributions
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


def test_committed_artifact_is_drawable():
    """Every curve in the shipped file satisfies MetricDistribution.

    The invariants themselves live on the model, so this is only asserting
    that the committed artifact passes them -- not restating what they are.
    """
    read_distributions(DISTRIBUTIONS_PATH)


@pytest.mark.parametrize(
    ("curve", "expected"),
    [
        ({"x": [1.0, 2.0], "density": [1.0], "cdf": [1.0]}, "same length"),
        ({"x": [], "density": [], "cdf": []}, "no bins"),
        ({"x": [2.0, 1.0], "density": [0.5, 0.5], "cdf": [0.5, 1.0]}, "must ascend"),
        ({"x": [1.0, 2.0], "density": [0.5, 0.5], "cdf": [1.0, 0.5]}, "non-decreasing"),
        ({"x": [1.0], "density": [1.0], "cdf": [0.4]}, "must reach 1.0"),
    ],
)
def test_rejects_a_curve_no_client_could_draw(tmp_path, curve, expected):
    """A ragged or truncated curve raises nowhere. It just draws wrong.

    So it has to fail on read, with the metric named, rather than reach a
    client. `response_model` would not catch any of these.
    """
    source = tmp_path / "distributions.json"
    source.write_text(json.dumps({"Overall": {"Complexity": {**curve, "min": 1.0, "max": 2.0}}}))
    with pytest.raises(DistributionsUnavailableError, match=expected):
        read_distributions(source)


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
    """A missing field fails on read rather than reaching a client.

    `response_model` would not catch it: returning a `Response` bypasses it,
    and even enforced it drops unknown keys rather than rejecting them.
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

    monkeypatch.setattr(distributions, "load_distributions", unavailable)
    response = client.get("/api/distributions")
    assert response.status_code == 503
    assert "missing" in response.json()["detail"]
