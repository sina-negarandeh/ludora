"""SearchService's query normalization.

The two retrieval legs disagreed about case. `websearch_to_tsquery`
lowercases while building lexemes, so lexical search never cared; the
embedding model does, so semantic search returned a different neighbourhood
for "catan" than for "Catan", and hybrid inherited it through the RRF union.
Measured against the live catalog before the fix: 149 hybrid matches topped
by "Catan: Big Box" against 120 topped by "Catan Card Game".

It was reachable from an ordinary keyboard rather than a contrived one. iOS
capitalizes the first letter of a search field by default, so the phone and
the web returned different games for the same keystrokes.

Both legs are pinned, not just the semantic one. Normalization is a no-op
for lexical in the sense that `websearch_to_tsquery` would fold the same
input anyway, but an untested call is one a later edit can delete without
anything failing, so the tsquery leg captures what it was handed too.

Nothing here touches the database or MLX -- `app.core.embeddings` defers its
`mlx` import into `_get_model`, so the module imports on any platform, and
the session is a stub.
"""
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.core import embeddings
from app.core.query_text import normalize_query
from app.schemas.search import SearchMode, SearchQuery
from app.services import search_service
from app.services.search_service import SearchService


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Catan", "catan"),
        ("CATAN", "catan"),
        ("catan", "catan"),
        ("  Ticket to Ride  ", "ticket to ride"),
        ("Terraforming MARS", "terraforming mars"),
        # Internal runs split a query the same way the ends do: one query to
        # the person typing, two different strings to the encoder.
        ("worker  placement", "worker placement"),
        ("\tGloomhaven\n", "gloomhaven"),
    ],
)
def test_normalize_folds_case_and_whitespace(raw, expected):
    assert normalize_query(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "\t\n  "])
def test_normalize_reduces_blank_input_to_empty(raw):
    # Callers treat this as "no query". An empty string is a perfectly good
    # input to an embedding model, and its nearest neighbours are arbitrary.
    assert normalize_query(raw) == ""


def test_normalize_folds_the_german_sharp_s():
    # `lower()` leaves the sharp s alone, so "Strasse" and "Straße" would
    # stay distinct strings and encode to distinct vectors. BGG's catalog is
    # full of German titles, so this is the same split the fold exists to
    # close, on a narrower class of input.
    assert normalize_query("Straße") == normalize_query("STRASSE")


def test_normalize_keeps_accents():
    # The lexical leg leans on the 'english_unaccent' config to match
    # "Chvatil" against "Chvátil"; roughly 9-10% of designers and artists
    # have non-ASCII names. Stripping diacritics here would move that
    # decision out of Postgres and break it.
    assert normalize_query("Vlaada CHVÁTIL") == "vlaada chvátil"


def test_normalize_is_idempotent():
    # Applied in both retrieval legs rather than once in `search`, so that a
    # direct caller of either gets the guarantee too. That is only safe
    # because a second application changes nothing.
    once = normalize_query("  Brass:   Birmingham ")
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


@pytest.fixture
def tsqueried(monkeypatch):
    """Captures what actually reaches `websearch_to_tsquery`."""
    seen: list[str] = []

    class _Func:
        @staticmethod
        def websearch_to_tsquery(config, text):
            seen.append(text)
            return object()

        @staticmethod
        def ts_rank_cd(*args, **kwargs):
            return _Orderable()

    class _Orderable:
        def desc(self):
            return self

    monkeypatch.setattr(search_service, "func", _Func)
    return seen


@pytest.mark.parametrize("raw", ["Catan", "CATAN", "  catan  "])
def test_semantic_leg_encodes_the_normalized_query(encoded, raw):
    _service().search_semantic(raw)
    assert encoded == ["catan"]


@pytest.mark.parametrize("raw", ["Catan", "CATAN", "  catan  ", "\tcatan\n"])
def test_lexical_leg_builds_the_tsquery_from_the_normalized_query(tsqueried, raw):
    _service().search_lexical(raw)
    assert tsqueried == ["catan"]


def test_hybrid_encodes_the_same_query_whatever_the_caller_typed(encoded):
    service = _service()
    service.search(SearchQuery(q="Catan", mode=SearchMode.HYBRID), skip=0, limit=10)
    service.search(SearchQuery(q="catan", mode=SearchMode.HYBRID), skip=0, limit=10)
    assert encoded == ["catan", "catan"]


@pytest.mark.parametrize("raw", ["", "   "])
def test_blank_query_retrieves_nothing_rather_than_anything(encoded, tsqueried, raw):
    # A blank field used to answer with 100 arbitrary games in semantic and
    # hybrid while lexical answered with none. Verified against the live
    # catalog: q="   " returned total 0, 100 and 100 for the three modes.
    service = _service()
    assert service.search_semantic(raw) == {}
    assert service.search_lexical(raw) == {}
    # Nothing was sent anywhere: no wasted encode, no query for nothing.
    assert encoded == []
    assert tsqueried == []


@pytest.mark.parametrize("mode", list(SearchMode))
def test_blank_query_returns_no_results_in_every_mode(encoded, tsqueried, mode):
    page = _service().search(SearchQuery(q="  ", mode=mode), skip=0, limit=10)
    assert page.total == 0
    assert page.items == []
