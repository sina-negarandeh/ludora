"""drop unused reviews created_at column

Revision ID: 7504c1be2bde
Revises: f46da67cfb4f
Create Date: 2026-08-17 12:47:46.564413

Confirmed NULL across all 4.2M rows in the jvanelteren review source — the
raw data never carried a per-review timestamp, so nothing populates this
column. Downgrade recreates it empty; there is no data to restore.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7504c1be2bde'
down_revision: Union[str, Sequence[str], None] = 'f46da67cfb4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('reviews', 'created_at')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('reviews', sa.Column('created_at', sa.DateTime(), nullable=True))
