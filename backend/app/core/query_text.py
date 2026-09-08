"""Normalization for user-typed search text.

Lives in `core` rather than in either service because both retrieval paths
need it and they do not import each other: `SearchService` (`/api/search/`)
and `GameService.get_games` (`/api/games/?query=`) are separate entry points
that a user cannot tell apart from the search field in front of them.
"""


def normalize_query(q: str) -> str:
    """Case- and whitespace-fold a search query.

    The two retrieval legs disagreed about case. `websearch_to_tsquery`
    lowercases while building its lexemes, so lexical search was already
    case-insensitive; the embedding model is not, so semantic search returned
    a different neighbourhood for "catan" than for "Catan" and hybrid
    inherited the difference through the RRF union. Measured against the live
    catalog: 149 hybrid matches topped by "Catan: Big Box" for the first,
    120 topped by "Catan Card Game" for the second.

    That is reachable from an ordinary keyboard, which is what makes it a
    bug rather than a quirk: iOS capitalizes the first letter of a search
    field by default, so the phone and the web returned different games for
    the same keystrokes.

    `casefold`, not `lower`, because this is a case-insensitive *comparison*
    rather than a display transform. `lower` leaves the German sharp s alone,
    so "Straße" and "STRASSE" stay distinct strings and encode to distinct
    vectors; `casefold` maps both to "strasse". BoardGameGeek's catalog is
    full of German titles, so that is the same split this function exists to
    close, on a narrower class of input.

    `split()` then `join`, not `strip()`, because internal runs of whitespace
    split the query the same way the ends do. "worker  placement" and
    "worker placement" are one query to the person typing and two different
    strings to the encoder. The lexical leg never cared either way, since
    `websearch_to_tsquery` tokenizes.

    Folding to this form leaves the committed search baseline meaning what it
    says: every query in `backend/evaluation/search_queries.json` is already
    lowercase, single-spaced ASCII, so this is the identity on all five and
    the numbers in `backend/evaluation/results/` were measured under exactly
    the condition this now guarantees.

    Documents are embedded with their natural case
    (`scripts/update_embeddings.py` does not fold), so this does leave the
    query slightly out of step with the corpus. That asymmetry is not new:
    it already applied to every lowercase query anyone typed, including all
    five evaluation queries. This makes it uniform instead of dependent on
    whether the caller happened to hold shift.

    Returns the empty string for input that is empty or only whitespace.
    Callers must treat that as "no query" rather than passing it on: an
    empty string is a perfectly good input to an embedding model, and its
    nearest neighbours are arbitrary games.
    """
    return " ".join(q.split()).casefold()
