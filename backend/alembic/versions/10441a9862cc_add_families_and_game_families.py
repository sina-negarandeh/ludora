"""add families and game_families

Revision ID: 10441a9862cc
Revises: a19f6c3e8d47
Create Date: 2026-08-16 23:06:38.392482

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10441a9862cc'
down_revision: Union[str, Sequence[str], None] = 'a19f6c3e8d47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # BGG Family (boardgamefamily), grouped by namespace (e.g. "Animals",
    # "Mechanism", "Theme", "Crowdfunding") — the full, ungrouped field, all
    # 72 namespaces including Theme: (which is also separately extracted
    # into the themes table today; consolidating them is a later decision).
    op.create_table(
        'families',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_name', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_families_group_name'), 'families', ['group_name'], unique=False)
    op.create_index(op.f('ix_families_name'), 'families', ['name'], unique=True)

    op.create_table(
        'game_families',
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.bgg_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('game_id', 'family_id'),
    )
    op.create_index(op.f('ix_game_families_family_id'), 'game_families', ['family_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_game_families_family_id'), table_name='game_families')
    op.drop_table('game_families')

    op.drop_index(op.f('ix_families_name'), table_name='families')
    op.drop_index(op.f('ix_families_group_name'), table_name='families')
    op.drop_table('families')
