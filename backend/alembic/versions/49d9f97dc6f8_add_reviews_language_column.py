"""add reviews language column

Revision ID: 49d9f97dc6f8
Revises: 629567b8e65f
Create Date: 2026-08-17 11:55:05.324698

Backfills nothing by itself — detected via fastText and populated by
scripts/detect_languages.py, which now finds the column ready instead of
requiring the ad hoc scripts/alter_table.py to have been run first.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49d9f97dc6f8'
down_revision: Union[str, Sequence[str], None] = '629567b8e65f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reviews', sa.Column('language', sa.String(length=10), nullable=True))
    op.create_index(op.f('ix_reviews_language'), 'reviews', ['language'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_reviews_language'), table_name='reviews')
    op.drop_column('reviews', 'language')
