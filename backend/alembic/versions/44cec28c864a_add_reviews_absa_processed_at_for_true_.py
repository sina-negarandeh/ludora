"""add reviews absa_processed_at for true resumability

Revision ID: 44cec28c864a
Revises: 129f9cdc157b
Create Date: 2026-08-18 08:50:33.624325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44cec28c864a'
down_revision: Union[str, Sequence[str], None] = '129f9cdc157b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reviews', sa.Column('absa_processed_at', sa.DateTime(), nullable=True))
    # Partial index matching absa_extract_hf.py's exact query shape
    # (WHERE is_absa_eligible AND absa_processed_at IS NULL ORDER BY
    # quality_score DESC) -- this table is ~4.2M rows, so an index tailored
    # to the resumable-run query matters for repeated --minutes-bounded runs.
    op.execute(
        "CREATE INDEX ix_reviews_absa_unprocessed ON reviews (quality_score DESC) "
        "WHERE is_absa_eligible = true AND absa_processed_at IS NULL"
    )
    # Backfill: reviews that already produced at least one stored aspect are
    # genuinely done and should never be reprocessed. Reviews that were
    # attempted but yielded zero evidence-matched aspects (the bug this
    # migration fixes) aren't identifiable after the fact without
    # re-running inference -- they get one harmless extra pass under the
    # new code, then are correctly marked from then on.
    op.execute(
        "UPDATE reviews SET absa_processed_at = now() "
        "WHERE id IN (SELECT DISTINCT review_id FROM review_aspects WHERE review_id IS NOT NULL)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_reviews_absa_unprocessed")
    op.drop_column('reviews', 'absa_processed_at')
