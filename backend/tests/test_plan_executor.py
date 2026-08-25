"""Tests for the LangGraph plan walk, especially its one cycle.

Deliberately infra-free -- no database, no LLM server -- by driving the
graph with a fake orchestrator. All the walk asks of one is
`execute(intent, known_bgg_ids) -> AssistantResponse`. The thing under
test is control flow (which steps run, in what order, when the relax
cycle fires and when it stops), and that is exactly what a fake can
exercise honestly. Wiring the real orchestrator in would test SQLAlchemy
and the browse service instead, and would not run in CI.

The message helpers are covered here too: they are pure functions over
the walk's output, so they need no orchestrator at all.

The cycle is the property most worth pinning: it drops one bound at a
time and stops at the first set that matches, so it must relax as little
as possible and must always terminate.
"""

from app.schemas.assistant import AssistantResponse, GameFilters, ParsedIntent, ParsedPlan
from app.schemas.game_query import SortSpec
from app.services.assistant_orchestrator import based_on_prefix, relaxation_note
from app.services.plan_executor import run_plan
from app.services.plan_graph import compile_plan


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
        self.known_seen: list[dict] = []

    def execute(self, intent: ParsedIntent, known_bgg_ids: dict | None = None) -> AssistantResponse:
        self.executed.append(intent)
        self.known_seen.append(dict(known_bgg_ids or {}))

        if self.fail_on is not None and len(self.executed) - 1 == self.fail_on:
            return AssistantResponse(
                message="something went wrong", type="error",
                parsed_intent=intent, data={},
            )

        # Only min_complexity makes this step unsatisfiable. Any other
        # bound the step carries is satisfiable, so a recovery pass that
        # drops more than min_complexity has relaxed more than it needed.
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
    assert state["relaxed_filters"] == {0: ["min_complexity"]}
    # The point of recovering at all: the dependent step gets the game the
    # retry found. Asserting only the filters would let a relax that
    # produced results but broke the substitution pass.
    assert orch.executed[2].game_name == "Found Game"


def test_cycle_terminates_when_every_bound_has_been_given_up():
    """The bound on the cycle. Each pass gives up exactly one more
    filter, so a step that never matches runs out of things to drop and
    stops, rather than looping until LangGraph's recursion limit."""
    orch = FakeOrchestrator(always_empty=True)
    state = _run(orch, _plan(GameFilters(min_complexity=4.9, min_playtime=90)))

    # Original run, then one retry per bound dropped, then nothing left.
    assert [i.intent for i in orch.executed] == ["browse", "browse", "browse"]
    assert state["relaxed_filters"] == {0: ["min_complexity", "min_playtime"]}
    # The dependent step never runs, and the user gets the step's own
    # explanation rather than an internal-sounding one.
    assert 1 not in state["results"]
    assert state["final"] is not None
    assert state["final"].message == "I couldn't find any games matching your preferences."


def test_relaxation_is_minimal_and_keeps_what_the_user_asked_for():
    """Regression against over-relaxing.

    Only min_complexity makes the fake's step unsatisfiable, so recovery
    must give that up and stop -- keeping min_playtime, which the user
    did ask about and which was never the problem. Dropping every bound
    in one pass would answer a looser question than necessary.
    """
    orch = FakeOrchestrator()
    state = _run(orch, _plan(GameFilters(min_playtime=90, min_complexity=4.9)))

    assert state["relaxed_filters"] == {0: ["min_complexity"]}
    retried = orch.executed[1].filters
    assert retried is not None
    assert retried.min_complexity is None
    assert retried.min_playtime == 90


def test_names_resolved_by_an_earlier_step_reach_the_handler():
    """known_bgg_ids belongs to one plan execution, so the walk carries
    it and hands it to each step, rather than the orchestrator holding it
    as mutable instance state reset by convention."""
    orch = FakeOrchestrator()
    _run(orch, _plan(GameFilters(subdomains=["Party"])))

    # Step 0 has nothing resolved yet; step 1 runs against the exact id
    # step 0 produced, so it can skip the fuzzy resolver.
    assert orch.known_seen[0] == {}
    assert orch.known_seen[1] == {"Found Game": 42}


def test_no_relax_when_there_is_no_model_invented_bound_to_drop():
    orch = FakeOrchestrator(always_empty=True)
    state = _run(orch, _plan(GameFilters(subdomains=["Party"])))

    assert [i.intent for i in orch.executed] == ["browse"]
    assert state["relaxed_filters"] == {}


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
    assert state["relaxed_filters"] == {}


def test_a_failed_step_stops_the_walk():
    orch = FakeOrchestrator(fail_on=0)
    state = _run(orch, _plan(GameFilters(subdomains=["Party"])))

    assert [i.intent for i in orch.executed] == ["browse"]
    assert state["final"] is not None
    assert state["final"].type == "error"
    assert 1 not in state["results"]


# --- message helpers -------------------------------------------------
# Pure functions over the walk's output, so they need no orchestrator.
# They are the only user-visible product of recovery, and every branch
# here produces text a person reads.


def test_no_note_when_recovery_never_fired():
    assert relaxation_note({}) == ""


def test_note_for_one_relaxed_step_omits_the_step_number():
    note = relaxation_note({0: ["min_complexity"]})
    assert note == "Nothing matched every constraint, so I relaxed min_complexity. "


def test_note_keeps_the_order_bounds_were_given_up_in():
    """The order is the policy (_RELAXABLE_FILTERS runs least-defensible
    first), so it says which constraint was treated as most disposable.
    Sorting alphabetically would invent a different claim."""
    note = relaxation_note({0: ["min_playtime", "max_complexity"]})
    assert "min_playtime, max_complexity" in note


def test_note_attributes_bounds_per_step_when_several_relaxed():
    note = relaxation_note({0: ["min_complexity"], 1: ["max_playtime"]})
    assert note == (
        "Nothing matched every constraint, so I relaxed "
        "min_complexity on step 0; max_playtime on step 1. "
    )


def test_note_ignores_positions_that_dropped_nothing():
    """Regression: the single-step branch used to re-read the unfiltered
    dict, so an empty entry ahead of a real one rendered "I relaxed . "."""
    assert relaxation_note({0: []}) == ""
    note = relaxation_note({0: [], 1: ["min_complexity"]})
    assert note == "Nothing matched every constraint, so I relaxed min_complexity. "


def _found(*names) -> AssistantResponse:
    return AssistantResponse(
        message="ok", type="search_results",
        parsed_intent=ParsedIntent(intent="browse", step_id=0),
        data={"total": len(names),
              "games": [{"name": n, "bgg_id": 100 + i} for i, n in enumerate(names)]},
    )


def test_no_based_on_prefix_for_a_single_result():
    graph = compile_plan(_plan(None))
    assert based_on_prefix(graph, {0: _found("A")}) == ""


def test_based_on_prefix_names_the_single_chained_game():
    graph = compile_plan(_plan(None))
    prefix = based_on_prefix(graph, {0: _found("Brass"), 1: _found("Brass")})
    assert prefix == "Based on Brass: "


def test_based_on_prefix_counts_and_lists_several_suggestions():
    graph = compile_plan(_plan(None))
    prefix = based_on_prefix(graph, {0: _found("A", "B", "C"), 1: _found("A")})
    assert prefix == "Based on 3 suggestions (A, B, C): "


def test_no_based_on_prefix_when_two_independent_steps_merge():
    """With two sources feeding one compare there is no single "based on"
    to name, and the comparison's own data already shows both."""
    plan = ParsedPlan(steps=[
        ParsedIntent(intent="browse", limit=1, step_id=0),
        ParsedIntent(intent="browse", limit=1, step_id=1),
        ParsedIntent(intent="compare", game_names=["$step0", "$step1"],
                     depends_on_step=0, step_id=2),
    ])
    graph = compile_plan(plan)
    results = {0: _found("A"), 1: _found("B"), 2: _found("A", "B")}
    assert based_on_prefix(graph, results) == ""
