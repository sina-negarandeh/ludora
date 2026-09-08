"""Query normalization, and the layer it lives in.

The two retrieval legs disagreed about case. `websearch_to_tsquery`
lowercases while building lexemes, so lexical search never cared; the
embedding model does, so semantic search returned a different neighbourhood
for "catan" than for "Catan", and hybrid inherited it through the RRF union.
Measured against the live catalog before the fix: 149 hybrid matches topped
by "Catan: Big Box" against 120 topped by "Catan Card Game". Full account in
docs/ml/search.md#query-normalization.

The layer matters as much as the fold. Normalization happens where a query
enters -- validated onto `SearchQuery.q`, called directly by
`GameService.get_games` because that path has no model -- so the retrieval
legs stay pure and no caller has to remember. These tests pin the entry
points, not the legs, because that is where the guarantee now lives.

Nothing here touches the database or MLX: `app.core.embeddings` defers its
`mlx` import into `_get_model`, so the module imports on any platform, and
the sessions are stubs.
"""
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.core import embeddings
from app.core.query_text import normalize_query
from app.schemas.search import SearchMode, SearchQuery
from app.services import search_service
from app.services.game_service import GameService
from app.services.search_service import SearchService

# MARK: the fold itself


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
    once = normalize_query("  Brass:   Birmingham ")
    assert normalize_query(once) == once


# MARK: the entry points


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("  CATAN ", "catan"), ("Ticket  To  RIDE", "ticket to ride"), ("   ", "")],
)
def test_search_query_normalizes_on_construction(raw, expected):
    # Every caller builds one of these -- the route, the assistant, the
    # entity resolver, the evaluation harness -- so folding here is what
    # covers all of them without each one remembering.
    assert SearchQuery(q=raw, mode=SearchMode.HYBRID).q == expected


class _Chain:
    """Enough of a SQLAlchemy query to get to `.all()` and back."""

    def __init__(self, recorder=None):
        self.recorder = recorder

    def filter(self, *args, **kwargs):
        if self.recorder is not None:
            self.recorder.extend(args)
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def offset(self, *args, **kwargs):
        return self

    def with_entities(self, *args, **kwargs):
        return self

    def scalar(self):
        return 0

    def all(self):
        return []


class _Session:
    def __init__(self, recorder=None):
        self.recorder = recorder

    def query(self, *args, **kwargs):
        return _Chain(self.recorder)


def _service(recorder=None) -> SearchService:
    # Cast rather than a real Session: these paths only ever reach
    # `.query(...)` here, and standing up a real one would drag in the
    # database this suite is deliberately free of.
    return SearchService(cast(Session, _Session(recorder)))


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

    class _Orderable:
        def desc(self):
            return self

    class _Func:
        @staticmethod
        def websearch_to_tsquery(config, text):
            seen.append(text)
            return object()

        @staticmethod
        def ts_rank_cd(*args, **kwargs):
            return _Orderable()

    monkeypatch.setattr(search_service, "func", _Func)
    return seen


@pytest.mark.parametrize("raw", ["Catan", "CATAN", "  catan  ", "\tcatan\n"])
def test_search_sends_the_folded_query_to_both_legs(encoded, tsqueried, raw):
    # End to end through the entry point, because the legs no longer fold
    # anything themselves: this is what proves the guarantee survives the
    # move onto the contract.
    _service().search(SearchQuery(q=raw, mode=SearchMode.HYBRID), skip=0, limit=10)
    assert encoded == ["catan"]
    assert tsqueried == ["catan"]


@pytest.mark.parametrize("mode", list(SearchMode))
def test_blank_query_retrieves_nothing_rather_than_anything(encoded, tsqueried, mode):
    # A blank field used to answer with 100 arbitrary games in semantic and
    # hybrid while lexical answered with none. Verified against the live
    # catalog: q="   " returned total 0, 100 and 100 for the three modes.
    page = _service().search(SearchQuery(q="  ", mode=mode), skip=0, limit=10)

    assert page.total == 0
    assert page.items == []
    # Nothing was sent anywhere: no wasted encode, no query for nothing.
    assert encoded == []
    assert tsqueried == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("catan", "%catan%"), ("CATAN ", "%catan%"), ("  Ticket  to Ride", "%ticket to ride%")],
)
def test_browse_path_folds_before_building_its_like_pattern(raw, expected):
    # This path interpolates straight into a LIKE pattern, so an untrimmed
    # query needed a literal space after the name. Measured against the live
    # catalog: "catan" matched 46 games, "catan " matched 14.
    criteria: list = []
    GameService(cast(Session, _Session(criteria))).get_games(query_str=raw)

    patterns = [
        c.right.value
        for c in criteria
        if getattr(c, "operator", None) is not None and hasattr(c, "right")
    ]
    assert expected in patterns


def test_browse_path_treats_a_blank_query_as_no_query():
    criteria: list = []
    GameService(cast(Session, _Session(criteria))).get_games(query_str="   ")
    assert criteria == [], "a blank query should not become LIKE '%%'"


def test_filters_only_assistant_search_browses_instead_of_retrieving(monkeypatch):
    """A search with no text is a browse, and must reach the browse handler.

    The LLM routes "strategy games for four players" to `search` often
    enough. Retrieval has nothing to rank without a query, so the candidate
    pool comes back empty and the filters never run: this answered "I found
    0 games matching 'None'". Guarding inside the retrieval legs could not
    fix it, because that layer cannot see that filters exist.
    """
    from app.schemas.assistant import ParsedIntent
    from app.services.assistant_orchestrator import AssistantOrchestrator

    orchestrator = AssistantOrchestrator(cast(Session, _Session()))
    browsed: list[ParsedIntent] = []
    monkeypatch.setattr(
        orchestrator, "_handle_browse", lambda intent, known: browsed.append(intent)
    )

    for blank in (None, "", "   "):
        orchestrator._handle_search(ParsedIntent(intent="search", query=blank), {})

    assert len(browsed) == 3, "every text-free search should route to browse"


def test_entity_resolver_matches_a_title_the_canonical_way(monkeypatch):
    """Exact-match detection uses the same fold retrieval does.

    `.lower()` leaves the German sharp s alone, so "Straße" searched as
    "STRASSE" was not recognised as the exact match it plainly is, and the
    lookup fell through to the ambiguous branch. Two notions of equality in
    one lookup is one too many.
    """
    from types import SimpleNamespace

    from app.services.entity_resolver import EntityResolver

    def _hit(bgg_id, name):
        return SimpleNamespace(game=SimpleNamespace(bgg_id=bgg_id, name=name, year_published=2019))

    resolver = EntityResolver(cast(Session, _Session()))
    monkeypatch.setattr(
        resolver.search_service,
        "search",
        lambda *a, **k: SimpleNamespace(
            total=2, items=[_hit(1, "Straße"), _hit(2, "Strasse Extra")]
        ),
    )

    assert resolver.resolve_game("STRASSE") == 1
