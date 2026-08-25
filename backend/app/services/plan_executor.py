"""LangGraph state machine that executes a compiled PlanGraph.

Why a state machine and not the plain loop this replaces: the loop could
only ever move forward. `plan_graph.compile_plan` makes the plan acyclic
BY CONSTRUCTION (references must point strictly backward), which is the
right guarantee for a plan an LLM produced -- but it also means a step
that legitimately matches nothing can only dead-end. There is no way to
express "that came back empty, loosen it and try again," because that is
a cycle.

This graph adds exactly that one cycle (execute -> relax -> execute) and
nothing else. The plan itself is still validated by compile_plan first,
and still walked in position order; LangGraph owns only the control flow
between steps, not the plan's shape.

Topology is fixed and compiled once at import (see PLAN_EXECUTOR at the
bottom) -- the per-request plan travels through it as state, rather than
a new graph being built per request. That distinction matters: a
LangGraph StateGraph is a static topology, while a ParsedPlan is data.

    START -> resolve -> execute -> [route] -+-> relax -> execute  (cycle)
                                            +-> resolve           (next step)
                                            +-> END
"""
from typing import Any, Protocol, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.core.ml_config import AssistantConfig
from app.schemas.assistant import AssistantResponse, GameFilters, ParsedIntent
from app.services.plan_graph import PlanGraph, PlanStep

# Numeric range bounds get dropped on a relax pass; taxonomy filters and
# player counts do not. This isn't arbitrary: the parsing prompt's own
# rules 14 and 16 tell the model to INVENT these numbers when the user
# only said something vague ("light" -> max_complexity=2.0, "quick" ->
# max_playtime=30). So they're the model's guess at a soft preference,
# not something the user actually specified -- exactly the right thing
# to loosen first. Subdomains/categories/player counts are what the user
# concretely asked for, so relaxing those would answer a different
# question than the one posed.
_RELAXABLE_FILTERS = (
    "min_complexity", "max_complexity",
    "min_playtime", "max_playtime",
    "min_year", "max_year",
)

# These names are read off GameFilters by string, so a rename or typo
# would otherwise make every getattr() return None -- recovery would
# silently stop firing, with no error and nothing failing except the
# feature. Checked once at import so that becomes a startup crash.
_unknown_filters = set(_RELAXABLE_FILTERS) - set(GameFilters.model_fields)
if _unknown_filters:
    raise RuntimeError(
        f"_RELAXABLE_FILTERS names fields that don't exist on GameFilters: "
        f"{sorted(_unknown_filters)}"
    )


class SupportsPlanExecution(Protocol):
    """What this module actually needs from the orchestrator.

    Declared explicitly rather than typing the parameter as
    AssistantOrchestrator: that would be a circular import (the
    orchestrator imports run_plan from here), and stating the three
    methods makes the cross-module contract visible instead of leaving
    it as an undocumented dependency on someone else's internals.
    """

    def execute(self, intent: ParsedIntent) -> AssistantResponse: ...

    def resolve_step(self, node: PlanStep, results: dict) -> ParsedIntent | None: ...

    def extract_chainable_values(self, response: AssistantResponse) -> list: ...


class PlanState(TypedDict):
    """Everything the walk needs. `graph` is the compiled plan (data
    flowing through a fixed topology, see the module docstring);
    `relaxed` prevents a step from being loosened more than once, which
    is what keeps the one cycle here from being an unbounded loop.

    `relaxed_filters` maps position -> the bounds dropped from that step,
    keyed rather than flattened so a caller can say WHICH part of the
    request was loosened when more than one step relaxes.
    """
    graph: PlanGraph
    position: int
    current: ParsedIntent | None
    results: dict[int, AssistantResponse]
    relaxed: list[int]
    relaxed_filters: dict[int, list[str]]
    final: AssistantResponse | None


def _orchestrator(config: RunnableConfig) -> SupportsPlanExecution:
    """The orchestrator is passed per-invocation rather than held in
    state: it owns a live DB session and the request-scoped _known_bgg_ids
    map, neither of which is plan data.

    `configurable` is optional on RunnableConfig in general, but run_plan
    below always supplies it -- this graph is not reachable any other way.
    """
    orchestrator = config.get("configurable", {}).get("orchestrator")
    assert orchestrator is not None, "run_plan must supply an orchestrator"
    return orchestrator


def _dependents_of(graph: PlanGraph, position: int) -> bool:
    """Does any later step actually consume this step's result? Only then
    is an empty result worth recovering from -- if nothing depends on it,
    "no matches" is a complete and correct answer on its own.
    """
    return any(position in node.depends_on for node in graph.steps)


def _resolve(state: PlanState, config: RunnableConfig) -> dict[str, Any]:
    """Substitute any $stepN placeholders in the current step, reusing the
    orchestrator's own resolution logic rather than reimplementing it.
    """
    orch = _orchestrator(config)
    node = state["graph"].steps[state["position"]]

    if not node.depends_on:
        return {"current": node.intent}

    priors = [state["results"][p] for p in node.depends_on]
    bad = next((r for r in priors if r.type in ("error", "clarification")), None)
    if bad is None:
        bad = next((r for r in priors if not orch.extract_chainable_values(r)), None)
    if bad is not None:
        # Same principle as the non-graph path: the step that ran the
        # query already explained the outcome better than this layer can.
        return {"current": None, "final": bad}

    resolved = orch.resolve_step(node, state["results"])
    if resolved is None:
        return {"current": None, "final": AssistantResponse(
            message="That part of your request needed a single game from an earlier step, but more than one matched. Could you be more specific?",
            type="clarification",
            parsed_intent=node.intent,
            data={},
        )}
    return {"current": resolved}


def _execute(state: PlanState, config: RunnableConfig) -> dict[str, Any]:
    orch = _orchestrator(config)
    step = state["current"]
    assert step is not None  # _route_after_resolve sends us to END otherwise
    response = orch.execute(step)
    return {
        "results": {**state["results"], state["position"]: response},
        "final": response,
    }


def _relax(state: PlanState, config: RunnableConfig) -> dict[str, Any]:
    """Drop the model-invented numeric bounds from the current step and
    mark it relaxed so this can't fire twice for the same step.
    """
    step = state["current"]
    # Both guaranteed by _route_after_execute, which only routes here for
    # a step that has filters with at least one relaxable bound set.
    assert step is not None and step.filters is not None
    filters = step.filters
    dropped = [f for f in _RELAXABLE_FILTERS if getattr(filters, f, None) is not None]
    relaxed_filters = filters.model_copy(update=dict.fromkeys(dropped, None))
    return {
        "current": step.model_copy(update={"filters": relaxed_filters}),
        "relaxed": [*state["relaxed"], state["position"]],
        "relaxed_filters": {**state["relaxed_filters"], state["position"]: dropped},
    }


def _route_after_resolve(state: PlanState) -> str:
    return END if state["current"] is None else "execute"


def _route_after_execute(state: PlanState, config: RunnableConfig) -> str:
    """The one interesting decision in this graph.

    Recovery fires only when all of these hold, so it can never turn a
    complete answer into a different one:
      - the step matched nothing, AND
      - a later step needs its result (otherwise "no matches" IS the
        answer), AND
      - this step hasn't already been relaxed (bounds the cycle), AND
      - there is actually a model-invented bound to drop.
    """
    orch = _orchestrator(config)
    graph, position = state["graph"], state["position"]
    response = state["results"][position]

    if response.type not in ("error", "clarification"):
        empty = not orch.extract_chainable_values(response)
        step = state["current"]
        has_relaxable = step is not None and step.filters is not None and any(
            getattr(step.filters, f, None) is not None for f in _RELAXABLE_FILTERS
        )
        if (
            empty
            and _dependents_of(graph, position)
            and position not in state["relaxed"]
            and has_relaxable
        ):
            return "relax"

    if response.type in ("error", "clarification"):
        # Failure isolation: don't run later steps against known-bad state.
        return END
    if position + 1 < len(graph.steps):
        return "advance"
    return END


def _advance(state: PlanState) -> dict[str, Any]:
    return {"position": state["position"] + 1, "current": None}


def _build() -> Any:
    sg = StateGraph(PlanState)
    sg.add_node("resolve", _resolve)
    sg.add_node("execute", _execute)
    sg.add_node("relax", _relax)
    sg.add_node("advance", _advance)

    sg.add_edge(START, "resolve")
    sg.add_conditional_edges("resolve", _route_after_resolve, {"execute": "execute", END: END})
    sg.add_conditional_edges(
        "execute", _route_after_execute,
        {"relax": "relax", "advance": "advance", END: END},
    )
    sg.add_edge("relax", "execute")   # the cycle compile_plan forbids by design
    sg.add_edge("advance", "resolve")
    return sg.compile()


# Fixed topology, built once -- see the module docstring on why this
# isn't per-request.
PLAN_EXECUTOR = _build()


def _recursion_limit() -> int:
    """LangGraph counts every node run against a recursion limit whose
    default (25) has nothing to do with this plan's size, so derive it
    instead of inheriting it.

    Worst case per step is four node runs (resolve, execute, relax,
    execute) plus one advance between steps, so a MAX_PLAN_STEPS plan
    needs 5*steps. Doubling that leaves headroom for a topology change
    without silently turning a legal plan into a GraphRecursionError --
    which, not being an AgentRunError, would surface as an opaque 500
    rather than the 502 an upstream-model failure gets.
    """
    return max(25, AssistantConfig.MAX_PLAN_STEPS * 10)


def run_plan(orchestrator: SupportsPlanExecution, graph: PlanGraph) -> PlanState:
    initial: PlanState = {
        "graph": graph,
        "position": 0,
        "current": None,
        "results": {},
        "relaxed": [],
        "relaxed_filters": {},
        "final": None,
    }
    return PLAN_EXECUTOR.invoke(
        initial,
        config={
            "configurable": {"orchestrator": orchestrator},
            "recursion_limit": _recursion_limit(),
        },
    )
