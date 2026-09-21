#!/usr/bin/env python3
"""Assert that counts asserted in prose still match the repository.

The docs state a handful of numbers that are mechanically derivable: how many
Alembic migrations exist, how many pipeline scripts, how many REST endpoints.
Many sites across the doc set repeat them, and they went stale silently:
`migrations` and `scripts` were transposed for an unknown period, and a
hand-maintained tracking row had itself gone stale on all three numbers. A
careful manual correction pass still left four of seventeen sites wrong.

So the numbers are checked here rather than tracked by hand. Run by
`make docs-check`, and by `make check` alongside lint, typecheck, and test.

Detection is by noun, not by a list of known phrasings: any number appearing
just before "migrations", "scripts", or "endpoints" is treated as a claim
about the totals below. A new doc that states one is checked automatically,
which a list of known sentences would not do.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Up to three qualifier words are allowed between the number and the noun, so
# "27 tracked, reversible Alembic migrations" and "21 offline ETL/ML scripts"
# both match without naming either phrasing.
CLAIM = re.compile(r"\b(\d+)\s+(?:[A-Za-z/,.-]+\s+){0,3}(migrations|scripts|endpoints)\b")

SKIP_DIRS = {"node_modules", ".claude", ".git", ".venv", "venv"}


def migrations() -> int:
    return len(list((ROOT / "backend/alembic/versions").glob("*.py")))


def pipeline_scripts() -> int:
    """Only the top level of `scripts/`.

    Repo tooling lives in `scripts/tools/` precisely so it does not inflate
    the pipeline count the docs quote. This file is an example of that.
    """
    return len(list((ROOT / "scripts").glob("*.py")))


def endpoints() -> int:
    """Counted from route decorators, so no server or import is needed.

    `/health` is declared on the app in `main.py` rather than on a router, so
    it is counted separately. Missing it is how a "one off" discrepancy hides.
    """
    decorator = re.compile(r"@(?:app|router)\.(?:get|post|put|patch|delete)\(")
    sources = list((ROOT / "backend/app/api/routes").glob("*.py"))
    sources.append(ROOT / "backend/app/main.py")
    return sum(len(decorator.findall(p.read_text())) for p in sources)


def markdown_files() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*.md")
        if not SKIP_DIRS & set(p.relative_to(ROOT).parts)
    )


def main() -> int:
    actual = {
        "migrations": migrations(),
        "scripts": pipeline_scripts(),
        "endpoints": endpoints(),
    }

    wrong: list[str] = []
    checked = 0
    for path in markdown_files():
        rel = path.relative_to(ROOT)
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            for match in CLAIM.finditer(line):
                checked += 1
                claimed, noun = int(match.group(1)), match.group(2)
                if claimed != actual[noun]:
                    wrong.append(
                        f"  {rel}:{line_no}  says {claimed} {noun}, "
                        f"actual {actual[noun]}  ({match.group(0)!r})"
                    )

    summary = ", ".join(f"{v} {k}" for k, v in actual.items())
    if wrong:
        print(f"docs-check: {len(wrong)} of {checked} count claims are stale.", file=sys.stderr)
        print(f"actual: {summary}\n", file=sys.stderr)
        print("\n".join(wrong), file=sys.stderr)
        return 1

    print(f"docs-check: {checked} count claims match ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
