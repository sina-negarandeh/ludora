"""add reviews language confidence column

Revision ID: f46da67cfb4f
Revises: 49d9f97dc6f8
Create Date: 2026-08-17 12:04:08.501279

fastText's top-1 probability for the `language` guess. NULL means either
not yet processed or nothing to score (empty comment) — see
scripts/detect_languages.py for how the two are told apart via `language`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f46da67cfb4f'
down_revision: Union[str, Sequence[str], None] = '49d9f97dc6f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reviews', sa.Column('language_confidence', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reviews', 'language_confidence')
