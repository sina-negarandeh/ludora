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
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.core.ml_config import AssistantConfig
from app.schemas.assistant import AssistantResponse, GameFilters, ParsedIntent
from app.services.plan_graph import PlanGraph
from app.services.plan_resolution import extract_chainable_values, resolve_step

# Numeric range bounds get dropped on a relax pass; taxonomy filters and
# player counts do not. This isn't arbitrary: the parsing prompt's own
# rules 14 and 16 tell the model to INVENT these numbers when the user
# only said something vague ("light" -> max_complexity=2.0, "quick" ->
# max_playtime=30). So they're the model's guess at a soft preference,
# not something the user actually specified -- exactly the right thing
# to loosen first. Subdomains/categories/player counts are what the user
# concretely asked for, so relaxing those would answer a different
# question than the one posed.
# Order is the policy: the cycle drops these ONE AT A TIME, in this
# order, retrying after each, and stops at the first set that matches
# something. Dropping them all at once would over-relax -- measured
# against real data, "a quick, very heavy party game" has no matches,
# but dropping only min_complexity keeps 3 results that are still
# quick, whereas dropping everything also throws away the 30-minute
# limit the user did ask about.
#
# Least-defensible first. Complexity bounds are the most likely to be
# the model's own invention (rule 14 tells it to guess 2.0 for "light"),
# then playtime (rule 16, same), and year bounds last since "from the
# 2010s" is usually stated outright rather than inferred.
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


class PlanState(TypedDict):
    """Everything the walk needs. `graph` is the compiled plan (data
    flowing through a fixed topology, see the module docstring);
    `relaxed_filters` maps position -> the bounds already dropped from
    that step. It does double duty: it tells the caller WHICH part of the
    request was loosened (keyed rather than flattened, so two relaxed
    steps don't read as one over-constrained query), and it is what
    bounds the cycle -- each pass drops one more bound, so the graph can
    loop at most len(_RELAXABLE_FILTERS) times per step and then stops
    having anything left to give up.

    `known_bgg_ids` holds names an earlier step already resolved exactly.
    It lives here, not on the orchestrator, because it belongs to one
    plan execution and this is the thing that owns one plan execution.
    """
    graph: PlanGraph
    position: int
    current: ParsedIntent | None
    results: dict[int, AssistantResponse]
    known_bgg_ids: dict[str, int]
    relaxed_filters: dict[int, list[str]]
    final: AssistantResponse | None


def _orchestrator(config: RunnableConfig):
    """The orchestrator is passed per-invocation rather than held in
    state: it owns a live DB session, which is not plan data. The only
    thing this module asks of it is execute(intent, known_bgg_ids).

    `configurable` is optional on RunnableConfig in general, but run_plan
    below always supplies it -- this graph is not reachable any other way.
    """
    orchestrator = config.get("configurable", {}).get("orchestrator")
    assert orchestrator is not None, "run_plan must supply an orchestrator"
    return orchestrator


def _has_dependents(graph: PlanGraph, position: int) -> bool:
    """Does a later step consume this step's result? Only then is an
    empty result worth recovering from -- if nothing depends on it, "no
    matches" is a complete and correct answer on its own.
    """
    return any(position in node.depends_on for node in graph.steps)


def _next_bound_to_drop(step: ParsedIntent) -> str | None:
    """The next single bound this step can give up, or None when it has
    nothing left. Driving the cycle one bound at a time is what keeps
    recovery to the closest satisfiable question instead of the loosest.

    Termination is structural rather than guarded: _relax sets the bound
    it drops to None on the step it hands back, so each pass strictly
    reduces the number of non-None relaxable bounds, and there are
    finitely many. No separate "already dropped" bookkeeping is needed,
    and keeping some would only be a second way to say the same thing.
    """
    filters = step.filters
    if filters is None:
        return None
    return next((f for f in _RELAXABLE_FILTERS if getattr(filters, f) is not None), None)


def _resolve(state: PlanState, config: RunnableConfig) -> dict[str, Any]:
    """Fill in this step's $stepN placeholders from earlier results."""
    node = state["graph"].steps[state["position"]]

    if not node.depends_on:
        return {"current": node.intent}

    # A dependency that errored, asked for clarification, or matched
    # nothing can't feed this step. Surface its own response: the step
    # that ran the query already explained the outcome in the user's
    # terms, better than this layer restating it as an internal failure.
    priors = [state["results"][p] for p in node.depends_on]
    unusable = next(
        (r for r in priors
         if r.type in ("error", "clarification") or not extract_chainable_values(r)),
        None,
    )
    if unusable is not None:
        return {"current": None, "final": unusable}

    resolved = resolve_step(node, state["results"])
    if resolved is None:
        # Everything it depends on found something, so the only way here
        # is a count mismatch: a slot needing exactly one game matched
        # several, and picking one would be a guess at what was meant.
        return {"current": None, "final": AssistantResponse(
            message="That part of your request needed a single game from an earlier step, but more than one matched. Could you be more specific?",
            type="clarification",
            parsed_intent=node.intent,
            data={},
        )}
    step, newly_known = resolved
    return {
        "current": step,
        "known_bgg_ids": {**state["known_bgg_ids"], **newly_known},
    }


def _execute(state: PlanState, config: RunnableConfig) -> dict[str, Any]:
    step = state["current"]
    assert step is not None  # _route_after_resolve sends us to END otherwise
    response = _orchestrator(config).execute(step, state["known_bgg_ids"])
    return {
        "results": {**state["results"], state["position"]: response},
        "final": response,
    }


def _relax(state: PlanState, config: RunnableConfig) -> dict[str, Any]:
    """Give up exactly one more bound and let the cycle retry."""
    step = state["current"]
    assert step is not None and step.filters is not None
    position = state["position"]
    dropping = _next_bound_to_drop(step)
    # _route_after_execute only sends us here when one is available.
    assert dropping is not None

    return {
        "current": step.model_copy(
            update={"filters": step.filters.model_copy(update={dropping: None})}
        ),
        "relaxed_filters": {
            **state["relaxed_filters"],
            position: [*state["relaxed_filters"].get(position, []), dropping],
        },
    }


def _route_after_resolve(state: PlanState) -> str:
    return END if state["current"] is None else "execute"


def _route_after_execute(state: PlanState, config: RunnableConfig) -> str:
    """The one interesting decision in this graph.

    Recovery fires only when the step matched nothing AND a later step
    needs its result AND the step still has a bound left to give up, so
    it can never turn a complete answer into a looser one, and the cycle
    always terminates: every pass consumes one more bound.
    """
    graph, position = state["graph"], state["position"]
    response = state["results"][position]

    if response.type in ("error", "clarification"):
        # Failure isolation: don't run later steps against known-bad state.
        return END

    step = state["current"]
    if (
        not extract_chainable_values(response)
        and _has_dependents(graph, position)
        and step is not None
        and _next_bound_to_drop(step) is not None
    ):
        return "relax"

    return "advance" if position + 1 < len(graph.steps) else END


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

    Worst case per step is resolve, then one execute per bound the step
    can give up (relax + execute for each of _RELAXABLE_FILTERS), plus
    one advance: 2 + 2*len(_RELAXABLE_FILTERS). Doubling that leaves
    headroom for a topology change without silently turning a legal plan
    into a GraphRecursionError -- which, not being an AgentRunError,
    would surface as an opaque 500 rather than the 502 an upstream-model
    failure gets.
    """
    per_step = 2 + 2 * len(_RELAXABLE_FILTERS)
    return max(25, AssistantConfig.MAX_PLAN_STEPS * per_step * 2)


def run_plan(orchestrator, graph: PlanGraph) -> PlanState:
    initial: PlanState = {
        "graph": graph,
        "position": 0,
        "current": None,
        "results": {},
        "known_bgg_ids": {},
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
