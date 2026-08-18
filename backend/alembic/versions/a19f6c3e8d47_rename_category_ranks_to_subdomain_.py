"""Rename games.category_ranks to subdomain_ranks

Revision ID: a19f6c3e8d47
Revises: e7a2c58f9b16
Create Date: 2026-08-16 17:00:00.000000

Same mislabeling as the categories/themes/subdomains split (see
e7a2c58f9b16): this JSON column has always held per-subdomain rank
(Strategy Game Rank, Party Game Rank, etc.), not per-category rank.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a19f6c3e8d47'
down_revision: Union[str, Sequence[str], None] = 'e7a2c58f9b16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('games', 'category_ranks', new_column_name='subdomain_ranks')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('games', 'subdomain_ranks', new_column_name='category_ranks')
