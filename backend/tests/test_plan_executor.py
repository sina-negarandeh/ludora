"""Tests for the LangGraph plan walk, especially its one cycle.

Deliberately infra-free -- no database, no LLM server -- by driving the
graph with a fake orchestrator that satisfies
plan_executor.SupportsPlanExecution. The thing under test is control
flow (which steps run, in what order, when the relax cycle fires and
when it stops), and that is exactly what a fake can exercise honestly.
Wiring the real orchestrator in would test SQLAlchemy and the browse
service instead, and would not run in CI.

The cycle's bound is the property most worth pinning: `relax` must fire
at most once per step, or a step that stays empty would loop forever.
"""
from langchain_core.runnables import RunnableConfig

from app.schemas.assistant import AssistantResponse, GameFilters, ParsedIntent, ParsedPlan
from app.schemas.game_query import SortSpec
from app.services.plan_executor import PlanState, _route_after_execute, run_plan
from app.services.plan_graph import PlanStep, compile_plan


class FakeOrchestrator:
    """Stands in for AssistantOrchestrator.

    execute() decides its answer from the intent itself rather than a
    scripted queue, so re-execution after a relax pass is modelled the
    way it really behaves: the step is over-constrained while
    min_complexity is set, and finds something once that bound is gone.
    `always_empty` keeps a step empty even after relaxing, which is how
    the unbounded-loop case gets exercised.
    """

    def __init__(self, always_empty: bool = False, fail_on: int | None = None):
        self.always_empty = always_empty
        self.fail_on = fail_on
        self.executed: list[ParsedIntent] = []

    def execute(self, intent: ParsedIntent) -> AssistantResponse:
        self.executed.append(intent)

        if self.fail_on is not None and len(self.executed) - 1 == self.fail_on:
            return AssistantResponse(
                message="something went wrong", type="error",
                parsed_intent=intent, data={},
            )

        over_constrained = intent.filters is not None and intent.filters.min_complexity is not None
        if self.always_empty or over_constrained:
            return AssistantResponse(
                message="I couldn't find any games matching your preferences.",
                type="search_results", parsed_intent=intent,
                data={"total": 0, "games": []},
            )

        return AssistantResponse(
            message="Found it.", type="search_results", parsed_intent=intent,
            data={"total": 1, "games": [{"name": "Found Game", "bgg_id": 42}]},
        )

    def extract_chainable_values(self, response: AssistantResponse) -> list:
        games = (response.data or {}).get("games") or []
        return [(g["name"], g["bgg_id"]) for g in games]

    def resolve_step(self, node: PlanStep, results: dict) -> ParsedIntent | None:
        if node.game_name_ref is None:
            return node.intent
        values = self.extract_chainable_values(results[node.game_name_ref])
        if len(values) != 1:
            return None
        return node.intent.model_copy(update={"game_name": values[0][0]})


def _plan(step0_filters: GameFilters | None) -> ParsedPlan:
    """A two-step plan: step 1 needs the game step 0 finds."""
    return ParsedPlan(steps=[
        ParsedIntent(
            intent="browse", filters=step0_filters,
            sort=SortSpec(field="rating", direction="desc"), limit=1, step_id=0,
        ),
        ParsedIntent(
            intent="get_game", game_name="$step0",
            requested_facts=["rating"], depends_on_step=0, step_id=1,
        ),
    ])


def _run(orch, plan: ParsedPlan):
    return run_plan(orch, compile_plan(plan))


def test_linear_walk_executes_every_step_in_order():
    orch = FakeOrchestrator()
    state = _run(orch, _plan(GameFilters(subdomains=["Party"])))

    assert [i.intent for i in orch.executed] == ["browse", "get_game"]
    assert sorted(state["results"]) == [0, 1]
    # The dependent step ran against the name step 0 actually produced.
    assert orch.executed[1].game_name == "Found Game"
    assert state["relaxed"] == []
    assert state["relaxed_filters"] == {}


def test_relax_fires_when_an_over_constrained_step_blocks_a_dependent():
    orch = FakeOrchestrator()
    state = _run(orch, _plan(GameFilters(subdomains=["Party"], min_complexity=4.9)))

    # browse (empty) -> browse again with the bound dropped -> get_game
    assert [i.intent for i in orch.executed] == ["browse", "browse", "get_game"]
    first, retried = orch.executed[0].filters, orch.executed[1].filters
    assert first is not None and retried is not None
    assert first.min_complexity == 4.9
    assert retried.min_complexity is None
    # Taxonomy is what the user actually asked for -- it must survive.
    assert retried.subdomains == ["Party"]
    assert state["relaxed"] == [0]
    assert state["relaxed_filters"] == {0: ["min_complexity"]}


def test_relax_fires_at_most_once_so_the_cycle_terminates():
    """End-to-end: a step that stays empty after relaxing must stop,
    not loop until LangGraph's recursion limit."""
    orch = FakeOrchestrator(always_empty=True)
    state = _run(orch, _plan(GameFilters(subdomains=["Party"], min_complexity=4.9)))

    # Exactly two browse runs: the original and the single relaxed retry.
    assert [i.intent for i in orch.executed] == ["browse", "browse"]
    assert state["relaxed"] == [0]
    # The dependent step never runs, and the user gets the step's own
    # explanation rather than an internal-sounding one.
    assert 1 not in state["results"]
    assert state["final"] is not None
    assert state["final"].message == "I couldn't find any games matching your preferences."


def test_already_relaxed_step_is_never_relaxed_again():
    """Pins the `relaxed` guard on its own.

    Worth a direct test because the end-to-end path above cannot reach
    it: _relax drops every relaxable bound in one pass, so has_relaxable
    is already False on the second visit and stops the cycle first.
    Deleting the `relaxed` check therefore breaks nothing today -- but
    it is the guard that would still hold if _relax ever dropped bounds
    one at a time, which is exactly the refinement someone would reach
    for next. Asserting the routing decision directly keeps that
    invariant covered instead of resting on an accident of ordering.
    """
    step = ParsedIntent(
        intent="browse", filters=GameFilters(min_complexity=4.9), limit=1, step_id=0,
    )
    graph = compile_plan(_plan(GameFilters(min_complexity=4.9)))
    empty = AssistantResponse(
        message="none", type="search_results", parsed_intent=step,
        data={"total": 0, "games": []},
    )
    # Every precondition for relaxing holds -- empty result, a dependent
    # step, a bound still available to drop -- except that position 0 has
    # already been relaxed once.
    state: PlanState = {
        "graph": graph, "position": 0, "current": step,
        "results": {0: empty}, "relaxed": [0],
        "relaxed_filters": {0: ["max_playtime"]}, "final": empty,
    }
    config: RunnableConfig = {"configurable": {"orchestrator": FakeOrchestrator()}}

    assert _route_after_execute(state, config) != "relax"


def test_no_relax_when_there_is_no_model_invented_bound_to_drop():
    orch = FakeOrchestrator(always_empty=True)
    state = _run(orch, _plan(GameFilters(subdomains=["Party"])))

    assert [i.intent for i in orch.executed] == ["browse"]
    assert state["relaxed"] == []


def test_no_relax_when_nothing_depends_on_the_empty_step():
    """An empty result nothing consumes is a complete answer, not a
    failure to recover from."""
    orch = FakeOrchestrator()
    plan = ParsedPlan(steps=[
        ParsedIntent(intent="get_game", game_name="Catan", step_id=0),
        ParsedIntent(
            intent="browse", filters=GameFilters(min_complexity=4.9),
            limit=1, step_id=1,
        ),
    ])
    state = _run(orch, plan)

    assert [i.intent for i in orch.executed] == ["get_game", "browse"]
    assert state["relaxed"] == []


def test_a_failed_step_stops_the_walk():
    orch = FakeOrchestrator(fail_on=0)
    state = _run(orch, _plan(GameFilters(subdomains=["Party"])))

    assert [i.intent for i in orch.executed] == ["browse"]
    assert state["final"] is not None
    assert state["final"].type == "error"
    assert 1 not in state["results"]


def test_relaxed_filters_are_attributed_to_the_step_they_came_from():
    """Keyed by position, so a caller can say which part of the request
    was loosened instead of pooling bounds from unrelated steps."""
    orch = FakeOrchestrator()
    state = _run(orch, _plan(GameFilters(min_playtime=90, min_complexity=4.9)))

    assert set(state["relaxed_filters"]) == {0}
    assert sorted(state["relaxed_filters"][0]) == ["min_complexity", "min_playtime"]
