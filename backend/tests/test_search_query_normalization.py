"""SearchService's query case folding.

The two retrieval legs disagreed about case. `websearch_to_tsquery`
lowercases while building lexemes, so lexical search never cared; the
embedding model does, so semantic search returned a different neighbourhood
for "catan" than for "Catan", and hybrid inherited it through the RRF union.
Measured against the live catalog before the fix: 149 hybrid matches topped
by "Catan: Big Box" against 120 topped by "Catan Card Game".

It was reachable from an ordinary keyboard rather than a contrived one. iOS
capitalizes the first letter of a search field by default, so the phone and
the web returned different games for the same keystrokes.

The semantic assertion is the one that matters: normalization is a no-op for
the lexical leg, so only the encoder call actually pins the bug. Nothing here
touches the database or MLX -- `app.core.embeddings` defers its `mlx` import
into `_get_model`, so the module imports on any platform, and the session is
a stub.
"""
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.core import embeddings
from app.schemas.search import SearchMode, SearchQuery
from app.services.search_service import SearchService, normalize_query


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Catan", "catan"),
        ("CATAN", "catan"),
        ("catan", "catan"),
        ("  Ticket to Ride  ", "ticket to ride"),
        ("Terraforming MARS", "terraforming mars"),
    ],
)
def test_normalize_folds_case_and_surrounding_space(raw, expected):
    assert normalize_query(raw) == expected


def test_normalize_is_idempotent():
    # Applied in both retrieval legs rather than once in `search`, so that a
    # direct caller of either gets the guarantee too. That is only safe
    # because a second application changes nothing.
    once = normalize_query("  Brass: Birmingham ")
    assert normalize_query(once) == once


class _Chain:
    """Enough of a SQLAlchemy query to get to `.all()` and back."""

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return []


class _Session:
    def query(self, *args, **kwargs):
        return _Chain()


def _service() -> SearchService:
    # Cast rather than a real Session: the retrieval legs only ever reach
    # `.query(...)` here, and standing up a real one would drag in the
    # database this suite is deliberately free of.
    return SearchService(cast(Session, _Session()))


@pytest.fixture
def encoded(monkeypatch):
    """Captures what actually reaches the embedding model."""
    seen: list[str] = []

    def _encode(texts, is_query=False):
        seen.extend(texts)
        return [[0.0] * 4 for _ in texts]

    monkeypatch.setattr(embeddings, "encode", _encode)
    return seen


@pytest.mark.parametrize("raw", ["Catan", "CATAN", "  catan  "])
def test_semantic_leg_encodes_the_normalized_query(encoded, raw):
    _service().search_semantic(raw)
    assert encoded == ["catan"]


def test_hybrid_encodes_the_same_query_whatever_the_caller_typed(encoded):
    service = _service()
    service.search(SearchQuery(q="Catan", mode=SearchMode.HYBRID), skip=0, limit=10)
    service.search(SearchQuery(q="catan", mode=SearchMode.HYBRID), skip=0, limit=10)
    assert encoded == ["catan", "catan"]
