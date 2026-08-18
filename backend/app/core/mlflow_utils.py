"""Shared MLflow tracking setup — local SQLite store, no server required.

Every training/precompute/evaluation script uses `tracked_run()` instead of
calling `mlflow.start_run()` directly, so the tracking URI and experiment
naming convention stay consistent everywhere. MLflow 3.x deprecated the raw
filesystem tracking backend in favor of a SQLite-backed local store — this
is still fully local and server-free, just a single `.db` file instead of a
directory tree. Run history, params, and metrics land in `mlruns/mlflow.db`;
artifacts land under `mlruns/artifacts/<experiment>/` (both gitignored —
browse everything with `uv run --project backend mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --port 5001`).
Port 5001, not MLflow's default 5000 -- on macOS (Monterey+), port 5000 is
bound by the system AirPlay Receiver, so `mlflow ui` on its default port
either fails to start or gets silently shadowed by that instead.

In the UI, click "Model training" (top-left, next to "GenAI") before
looking for runs -- the default "GenAI" view only shows Traces/Sessions
(MLflow's newer LLM-tracing API, `mlflow.trace()`), which this project
doesn't use, so it looks empty even when "Model training" > an
experiment > Runs shows everything logged via log_params()/log_metrics().
"""
import json
import os
from contextlib import contextmanager

import mlflow

# Resolves to <repo-root>/mlruns regardless of the invoking process's CWD —
# scripts run from repo root, services run from backend/, both land here.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_MLRUNS_DIR = os.path.join(_REPO_ROOT, "mlruns")
_TRACKING_DB = os.path.join(_MLRUNS_DIR, "mlflow.db")
_ARTIFACT_DIR = os.path.join(_MLRUNS_DIR, "artifacts")
os.makedirs(_ARTIFACT_DIR, exist_ok=True)
mlflow.set_tracking_uri(f"sqlite:///{_TRACKING_DB}")


def _get_or_create_experiment(name: str) -> str:
    """Get an experiment's ID, creating it with an explicit (absolute, CWD-
    independent) artifact location the first time it's seen."""
    existing = mlflow.get_experiment_by_name(name)
    if existing is not None:
        return existing.experiment_id
    artifact_location = f"file:{os.path.join(_ARTIFACT_DIR, name)}"
    return mlflow.create_experiment(name, artifact_location=artifact_location)


@contextmanager
def tracked_run(experiment: str, run_name: str = None):
    """Start an MLflow run under a given experiment.

    Experiments are grouped by technique family, not by individual model id,
    so that directly-comparable models land as separate *runs* within one
    experiment — MLflow's run-comparison table only compares runs within the
    same experiment, and "compare these algorithms side by side" is the
    whole point here (e.g. `recommender/collaborative` holds one run each
    for cf_item_cosine/cf_als, rather than two separate experiments).
    See docs/ml/model-cards/ for the full experiment-per-model map.

    Usage:
        with tracked_run("recommender/collaborative", run_name="cf_als_train"):
            mlflow.log_params({"factors": RecommenderConfig.CF_ALS_FACTORS})
            ...
            mlflow.log_metrics({"precision_at_10": 0.12})
            mlflow.log_artifact(model_path)

    LLM-prompted features (no trained model/hyperparameters — the prompt
    text is the thing that determines behavior) live under a separate
    `llm/` namespace and log a different shape: a prompt hash, latency,
    and an eval-dataset version, not conventional hyperparameters. See
    `llm/review_summarization` and `llm/intent_parsing`.
    """
    exp_id = _get_or_create_experiment(experiment)
    with mlflow.start_run(experiment_id=exp_id, run_name=run_name) as run:
        yield run


def write_results_json(name: str, data: dict) -> str:
    """Write an evaluation result to backend/evaluation/results/<name>_latest.json.

    Complements MLflow's full run history with a single, plain, version-
    controllable file — for anyone (or a doc) who wants the current number
    without opening the MLflow UI. Overwrites on every run by design; MLflow
    is the place to look for history across runs.
    """
    results_dir = os.path.join(_REPO_ROOT, "backend", "evaluation", "results")
    os.makedirs(results_dir, exist_ok=True)
    path = os.path.join(results_dir, f"{name}_latest.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path
