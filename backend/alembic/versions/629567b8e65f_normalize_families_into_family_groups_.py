"""normalize families into family groups and subfamilies

Revision ID: 629567b8e65f
Revises: 10441a9862cc
Create Date: 2026-08-16 23:14:04.786841

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '629567b8e65f'
down_revision: Union[str, Sequence[str], None] = '10441a9862cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Replace the flat families/game_families pair (previous migration) with
    # a proper two-level hierarchy: families = the 72 BGG namespaces
    # ("Animals", "Mechanism", "Theme", ...) as first-class rows, subfamilies
    # = the 4,208 specific values within a group, FK'd to their family.
    # Games link to the leaf level only (game_subfamilies) — a game is never
    # tagged with a bare group in the source data, so a direct game<->family
    # join table would just be derived/redundant. See docs/data/README.md.
    op.drop_table('game_families')
    op.drop_table('families')

    op.create_table(
        'families',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_families_name'), 'families', ['name'], unique=True)

    op.create_table(
        'subfamilies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_subfamilies_family_id'), 'subfamilies', ['family_id'], unique=False)
    op.create_index(op.f('ix_subfamilies_name'), 'subfamilies', ['name'], unique=True)

    op.create_table(
        'game_subfamilies',
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('subfamily_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.bgg_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subfamily_id'], ['subfamilies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('game_id', 'subfamily_id'),
    )
    op.create_index(op.f('ix_game_subfamilies_subfamily_id'), 'game_subfamilies', ['subfamily_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_game_subfamilies_subfamily_id'), table_name='game_subfamilies')
    op.drop_table('game_subfamilies')

    op.drop_index(op.f('ix_subfamilies_name'), table_name='subfamilies')
    op.drop_index(op.f('ix_subfamilies_family_id'), table_name='subfamilies')
    op.drop_table('subfamilies')

    op.drop_index(op.f('ix_families_name'), table_name='families')
    op.drop_table('families')

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
