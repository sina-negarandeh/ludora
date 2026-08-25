"""Turning a compiled plan step into a runnable one.

This is plan-shaped logic, not intent-dispatch logic, so it lives beside
plan_graph rather than on AssistantOrchestrator (whose job is "given an
intent, call the right service"). Keeping it here is also what lets
plan_executor import it directly: while these lived on the orchestrator,
the executor needed a Protocol to describe someone else's methods purely
to dodge a circular import.

Both functions are pure. Resolution used to write resolved names into a
mutable `_known_bgg_ids` map on the orchestrator, reset per request by
convention; resolve_step now returns those names alongside the step, and
the caller decides where to keep them (plan_executor keeps them in the
walk's own state, which is where per-execution data belongs).
"""
from app.schemas.assistant import AssistantResponse, ParsedIntent
from app.services.plan_graph import PlanStep

# Cap on how many games a "compare" request will fetch/render -- past
# this many, a comparison table stops being readable in the narrow
# assistant drawer.
MAX_COMPARE_GAMES = 5


def extract_chainable_values(response: AssistantResponse) -> list[tuple[str, int]]:
    """Pulls every (name, bgg_id) pair out of a step's result.

    Used when a dependent step needs every game an earlier step found (a
    "compare" one-to-many placeholder), and to check how many games a
    dependency resolved to when deciding whether a substitution is
    unambiguous. The bgg_id travels with the name so the handlers can
    skip re-resolving a title that is already exact.
    """
    if not response.data:
        return []
    games = response.data.get("games")
    if games:
        return [(g["name"], g["bgg_id"]) for g in games if g.get("name") and g.get("bgg_id")]
    results = response.data.get("results")
    if results:
        return [(r["game"]["name"], r["game"]["bgg_id"]) for r in results if r.get("game", {}).get("name") and r.get("game", {}).get("bgg_id")]
    recommendations = response.data.get("recommendations")
    if recommendations:
        return [(r["game"]["name"], r["game"]["bgg_id"]) for r in recommendations if r.get("game", {}).get("name") and r.get("game", {}).get("bgg_id")]
    game = response.data.get("game")
    if game and game.get("name") and game.get("bgg_id"):
        return [(game["name"], game["bgg_id"])]
    return []


def resolve_step(
    node: PlanStep, results: dict[int, AssistantResponse]
) -> tuple[ParsedIntent, dict[str, int]] | None:
    """Substitutes every "$stepN" placeholder in node.intent's
    game_name/game_names with real values drawn from `results`, per
    node.depends_on (already validated non-empty and, by compile_plan's
    guarantee, all already executed and present in `results`).

    Returns the runnable step plus the {name: bgg_id} pairs it
    substituted, or None if a referenced step's result can't supply what
    this step needs -- the caller turns that into a user-facing outcome
    rather than guessing forward.

    Those returned ids matter: the names came straight off an earlier
    GameResponse, so they are already exact, and the compare handler uses
    them to skip the fuzzy EntityResolver, which can still spuriously
    raise AmbiguousEntityError on an exact title (measured: "Witch Hunt"
    did this).

    Three shapes, all handled uniformly by resolving every distinct
    referenced position once and then applying it wherever it's used:

    - "game_name" is itself a placeholder: needs exactly one game.
    - "game_names" has exactly one placeholder entry: this is the one
      case a placeholder can stand for MULTIPLE games at once (e.g.
      "suggest some games and compare them") -- if the referenced step
      resolved to more than one game, every one of them is used, capped
      at MAX_COMPARE_GAMES, replacing the whole game_names list rather
      than merging with any sibling literal entries (measured directly
      against this server: the model paired a many-valued placeholder
      with a second, fabricated literal title that wasn't in the user's
      request at all).
    - "game_names" has two or more DISTINCT placeholder entries (e.g.
      ["$step0", "$step1"] -- "compare the heaviest game to the
      highest-rated game", two independent prior steps merging into one
      compare): each referenced step must resolve to exactly one game.
      Comparing two open-ended GROUPS of suggestions against each other
      isn't well defined, so if any of them resolves to more than one
      game, that's an error rather than a guess at which games from
      which group to pair.
    """
    step = node.intent
    resolved: dict[int, list[tuple[str, int]]] = {}
    for position in node.depends_on:
        values = extract_chainable_values(results[position])
        if not values:
            return None
        resolved[position] = values

    updates: dict = {}
    known: dict[str, int] = {}

    if node.game_name_ref is not None:
        values = resolved[node.game_name_ref]
        if len(values) != 1:
            return None
        name, bgg_id = values[0]
        known[name] = bgg_id
        updates["game_name"] = name

    if node.game_names_refs:
        # game_names_refs is only populated by compile_plan when it found
        # placeholder matches while iterating step.game_names, so
        # game_names is guaranteed non-None here.
        assert step.game_names is not None
        new_names = list(step.game_names)
        if len(node.game_names_refs) == 1:
            (idx, position), = node.game_names_refs.items()
            values = resolved[position]
            known.update(dict(values))
            if len(values) == 1:
                new_names[idx] = values[0][0]
            else:
                new_names = [name for name, _ in values[:MAX_COMPARE_GAMES]]
        else:
            for idx, position in node.game_names_refs.items():
                values = resolved[position]
                if len(values) != 1:
                    return None
                name, bgg_id = values[0]
                known[name] = bgg_id
                new_names[idx] = name
        updates["game_names"] = new_names

    return (step.model_copy(update=updates) if updates else step), known
