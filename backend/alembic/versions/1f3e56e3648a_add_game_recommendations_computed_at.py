"""add game_recommendations computed_at

Revision ID: 1f3e56e3648a
Revises: 44cec28c864a
Create Date: 2026-08-18 11:58:26.920962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f3e56e3648a'
down_revision: Union[str, Sequence[str], None] = '44cec28c864a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('game_recommendations', sa.Column('computed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('game_recommendations', 'computed_at')
