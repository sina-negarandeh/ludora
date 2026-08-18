"""add review_aspects raw sentiment probabilities

Revision ID: 129f9cdc157b
Revises: d91a4c7e3f28
Create Date: 2026-08-18 08:38:48.592611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '129f9cdc157b'
down_revision: Union[str, Sequence[str], None] = 'd91a4c7e3f28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('review_aspects', sa.Column('prob_positive', sa.Float(), nullable=True))
    op.add_column('review_aspects', sa.Column('prob_neutral', sa.Float(), nullable=True))
    op.add_column('review_aspects', sa.Column('prob_negative', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('review_aspects', 'prob_negative')
    op.drop_column('review_aspects', 'prob_neutral')
    op.drop_column('review_aspects', 'prob_positive')
