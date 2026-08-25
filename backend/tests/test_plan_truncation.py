"""AssistantService.parse_plan()'s MAX_PLAN_STEPS truncation.

Pure, infra-free logic with a real correctness argument attached, and
nothing was pinning it: steps are sorted by step_id BEFORE truncating, so
the highest step_ids are the ones dropped. Truncating in raw array order
instead could keep an arbitrary subset and strand a reference a surviving
step depends on, since a "$stepN" placeholder can only ever point at an
earlier step (see plan_graph.compile_plan).

Calls the truncation through a real AssistantService, but stubs the agent
so no LLM server is involved.
"""
from types import SimpleNamespace

import pytest

from app.core.ml_config import AssistantConfig
from app.schemas.assistant import ParsedIntent, ParsedPlan
from app.services.assistant_service import AssistantService


@pytest.fixture
def service(monkeypatch):
    """A real service with both agents replaced, so construction does no
    network work and parse_plan returns whatever the test scripts."""
    monkeypatch.setattr(AssistantService, "__init__", lambda self: None)
    svc = AssistantService()
    svc.plan_model = "stub"
    return svc


def _stub_agent(svc, plan: ParsedPlan):
    svc._plan_agent = SimpleNamespace(
        run_sync=lambda _msg: SimpleNamespace(output=plan, all_messages=lambda: [])
    )


def _steps(*step_ids) -> ParsedPlan:
    return ParsedPlan(steps=[
        ParsedIntent(intent="browse", limit=1, step_id=i) for i in step_ids
    ])


def test_a_plan_within_the_ceiling_is_untouched(service):
    _stub_agent(service, _steps(0, 1))
    assert [s.step_id for s in service.parse_plan("q").steps] == [0, 1]


def test_an_oversized_plan_drops_the_highest_step_ids(service):
    over = AssistantConfig.MAX_PLAN_STEPS + 2
    _stub_agent(service, _steps(*range(over)))

    kept = [s.step_id for s in service.parse_plan("q").steps]
    assert kept == list(range(AssistantConfig.MAX_PLAN_STEPS))


def test_truncation_sorts_before_cutting_so_it_cannot_strand_a_reference(service):
    """The regression this guards. Given steps arriving out of order,
    truncating by array position would keep {5, 0} and drop step 1, which
    step 5's "$step1" needs. Sorting first keeps the earliest ids, so
    every surviving reference still has its target.
    """
    monkey = ParsedPlan(steps=[
        ParsedIntent(intent="browse", limit=1, step_id=5),
        ParsedIntent(intent="browse", limit=1, step_id=0),
        ParsedIntent(intent="browse", limit=1, step_id=1),
        ParsedIntent(intent="get_game", game_name="$step1", depends_on_step=1, step_id=2),
    ])
    _stub_agent(service, monkey)

    kept = [s.step_id for s in service.parse_plan("q").steps]
    assert kept == [0, 1, 2]
    assert 5 not in kept
