import re
from dataclasses import dataclass, field
from typing import Optional
from app.schemas.assistant import ParsedIntent, ParsedPlan

_PLACEHOLDER_RE = re.compile(r"^\$step(\d+)$")


class PlanValidationError(Exception):
    """Raised by compile_plan() for a problem with the SHAPE of a plan --
    a self-reference, a forward reference, or a reference to a step that
    doesn't exist -- as opposed to something only discoverable at
    execution time (e.g. a referenced step's result not resolving to a
    usable game). Carries a plain-English reason so a future retry path
    can feed it back to the LLM instead of just discarding it.
    """
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass
class PlanStep:
    """One compiled node in a validated plan graph. `position` -- this
    step's index in step_id order -- is its identity everywhere in the
    orchestrator, never the model's own `step_id`: that field has been
    measured duplicated across steps in a single plan, so trusting it as
    an identity would let one step's result silently overwrite another's.
    """
    position: int
    intent: ParsedIntent
    depends_on: list[int]                      # deduped positions this step's placeholders reference, in first-seen order
    game_name_ref: Optional[int] = None         # position, if game_name is itself "$stepN"
    game_names_refs: dict[int, int] = field(default_factory=dict)  # {index in game_names: referenced position}


@dataclass
class PlanGraph:
    steps: list[PlanStep]  # position order == execution order == topological order (see compile_plan)


def compile_plan(plan: ParsedPlan) -> PlanGraph:
    """Turns a raw, LLM-produced ParsedPlan into a validated PlanGraph the
    orchestrator can execute without re-deriving or re-checking anything.
    If this returns normally, every "$stepN" reference in the plan points
    at an earlier, already-known-to-exist step -- the executor never has
    to handle an out-of-range or forward reference itself.

    References are required to point strictly backward (0 <= N <
    this step's position), which is also what every worked example in
    the prompt already does -- enforcing it here as a validation rule,
    rather than just hoping it holds, makes the graph acyclic BY
    CONSTRUCTION. That's why there's no separate cycle-detection pass
    below: a graph that can only ever point backward cannot contain a
    cycle, so position order is always a valid topological order for
    free, without needing a general graph algorithm for a problem this
    constrained (plans top out at MAX_PLAN_STEPS steps).
    """
    ordered = sorted(plan.steps, key=lambda s: s.step_id)
    steps: list[PlanStep] = []

    for position, intent in enumerate(ordered):
        depends_on: list[int] = []
        game_name_ref: Optional[int] = None
        game_names_refs: dict[int, int] = {}

        if intent.game_name:
            match = _PLACEHOLDER_RE.match(intent.game_name)
            if match:
                ref = _validate_reference(int(match.group(1)), position)
                game_name_ref = ref
                depends_on.append(ref)

        for idx, name in enumerate(intent.game_names or []):
            match = _PLACEHOLDER_RE.match(name)
            if match:
                ref = _validate_reference(int(match.group(1)), position)
                game_names_refs[idx] = ref
                depends_on.append(ref)

        seen: set[int] = set()
        deduped = [p for p in depends_on if not (p in seen or seen.add(p))]

        steps.append(PlanStep(
            position=position,
            intent=intent,
            depends_on=deduped,
            game_name_ref=game_name_ref,
            game_names_refs=game_names_refs,
        ))

    return PlanGraph(steps=steps)


def _validate_reference(n: int, position: int) -> int:
    if not (0 <= n < position):
        raise PlanValidationError(
            f'step {position} references "$step{n}", which is not an earlier step in the plan'
        )
    return n
