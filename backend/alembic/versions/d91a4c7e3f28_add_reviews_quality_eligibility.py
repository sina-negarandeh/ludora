"""add reviews.quality_score and reviews.is_absa_eligible

Revision ID: d91a4c7e3f28
Revises: c4d8f21a9e56
Create Date: 2026-08-18 01:15:00.000000

Replaces the old JSON-cache sampling approach (data/stratified_samples.json,
scripts/generate_stratified_sample.py — deleted) with persisted per-review
eligibility: at ~378K eligible reviews (measured against the full corpus,
not a capped sample), a DB column is the right tool, not a growing cache
file. scripts/filter_eligible_reviews.py computes both; absa_extract_hf.py
reads is_absa_eligible directly instead of a cache.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd91a4c7e3f28'
down_revision: Union[str, Sequence[str], None] = 'c4d8f21a9e56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reviews', sa.Column('quality_score', sa.Float(), nullable=True))
    op.add_column('reviews', sa.Column('is_absa_eligible', sa.Boolean(), nullable=True))
    op.create_index('ix_reviews_is_absa_eligible', 'reviews', ['is_absa_eligible'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_reviews_is_absa_eligible', table_name='reviews')
    op.drop_column('reviews', 'is_absa_eligible')
    op.drop_column('reviews', 'quality_score')
