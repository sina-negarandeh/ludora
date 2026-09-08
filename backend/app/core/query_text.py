"""Normalization for user-typed search text."""


def normalize_query(q: str) -> str:
    """Fold a search query for comparison: collapse whitespace, casefold.

    Applied where a query enters the system rather than at each retrieval
    leg: `SearchQuery.q` validates through this, and `GameService.get_games`
    calls it directly because that path has no model to hang it on.

    `casefold` rather than `lower` because this is a case-insensitive
    comparison, not a display transform: `lower` leaves the German sharp s
    alone, and BGG's catalog is full of German titles. Whitespace runs
    collapse rather than only trim, because an internal double space splits
    a query for the encoder exactly the way a leading one does.

    Blank input folds to "". Callers must treat that as "no query": an empty
    string is a perfectly good input to an embedding model, and its nearest
    neighbours are arbitrary games.

    Why this exists, what it measurably fixed, and the query/document
    asymmetry it leaves behind: docs/ml/search.md#query-normalization.
    """
    return " ".join(q.split()).casefold()
