"""add unaccent extension and english_unaccent text search config

Revision ID: c4d8f21a9e56
Revises: b8e1c4a29f37
Create Date: 2026-08-17 21:55:00.000000

Postgres's built-in 'english' text search config does not fold diacritics —
'Chvátil' and 'Chvatil' tokenize to different, non-matching lexemes. Measured
against the live catalog: ~9% of designers, ~10% of artists, 5% of publishers
have non-ASCII names, so a plain-keyboard search for any of them (no accent
reproduced) silently returned zero results. `english_unaccent` copies the
built-in 'english' config but runs the `unaccent` extension as a token filter
before English stemming, so both the indexed tsvector and the query need to
use this same config for accent-insensitive matching to actually take effect
end to end (see scripts/update_search_vectors.py and
SearchService.search_lexical()).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4d8f21a9e56'
down_revision: Union[str, Sequence[str], None] = 'b8e1c4a29f37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # CREATE TEXT SEARCH CONFIGURATION has no IF NOT EXISTS clause in
    # Postgres — this migration only ever runs once via Alembic's own
    # tracking, so that's fine.
    op.execute("""
        CREATE TEXT SEARCH CONFIGURATION public.english_unaccent
        ( COPY = pg_catalog.english )
    """)
    op.execute("""
        ALTER TEXT SEARCH CONFIGURATION public.english_unaccent
        ALTER MAPPING FOR hword, hword_part, word
        WITH unaccent, english_stem
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS public.english_unaccent")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
