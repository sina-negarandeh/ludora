"""Add richer game attributes and game_relations table

Revision ID: d4a8f21c6b93
Revises: ac71b3ec0405
Create Date: 2026-08-16 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a8f21c6b93'
down_revision: Union[str, Sequence[str], None] = 'ac71b3ec0405'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fields already computed by build_master_dataset.py but never loaded
    # into the schema (see docs/architecture/data-pipeline.md).
    op.add_column('games', sa.Column('min_playtime', sa.Integer(), nullable=True))
    op.add_column('games', sa.Column('max_playtime', sa.Integer(), nullable=True))
    op.add_column('games', sa.Column('bayes_avg_rating', sa.Float(), nullable=True))
    op.add_column('games', sa.Column('stddev_rating', sa.Float(), nullable=True))
    op.add_column('games', sa.Column('num_weight_votes', sa.Integer(), nullable=True))
    op.add_column('games', sa.Column('thumbnail_url', sa.String(), nullable=True))
    op.add_column('games', sa.Column('kickstarted', sa.Boolean(), nullable=True))
    op.add_column('games', sa.Column('is_reimplementation', sa.Boolean(), nullable=True))

    # jvanelteren poll data, replacing the dropped Threnjen best_players /
    # good_players / com_age_rec / language_ease (never referenced anywhere
    # in the app, superseded by the real vote breakdown instead of a single
    # flattened value).
    op.add_column('games', sa.Column('suggested_num_players', sa.JSON(), nullable=True))
    op.add_column('games', sa.Column('suggested_playerage', sa.JSON(), nullable=True))
    op.add_column('games', sa.Column('suggested_language_dependence', sa.JSON(), nullable=True))

    # jvanelteren boardgameexpansion / boardgameimplementation / boardgameintegration.
    # Source data links by name, not BGGId; related_game_id is null wherever
    # the name didn't resolve to an exact (case/whitespace-normalized) match
    # against a known game.
    op.create_table(
        'game_relations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('related_name', sa.String(), nullable=False),
        sa.Column('related_game_id', sa.Integer(), nullable=True),
        sa.Column('relation_type', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.bgg_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['related_game_id'], ['games.bgg_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_game_relations_game_id'), 'game_relations', ['game_id'], unique=False)
    op.create_index(op.f('ix_game_relations_related_game_id'), 'game_relations', ['related_game_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_game_relations_related_game_id'), table_name='game_relations')
    op.drop_index(op.f('ix_game_relations_game_id'), table_name='game_relations')
    op.drop_table('game_relations')

    op.drop_column('games', 'suggested_language_dependence')
    op.drop_column('games', 'suggested_playerage')
    op.drop_column('games', 'suggested_num_players')

    op.drop_column('games', 'is_reimplementation')
    op.drop_column('games', 'kickstarted')
    op.drop_column('games', 'thumbnail_url')
    op.drop_column('games', 'num_weight_votes')
    op.drop_column('games', 'stddev_rating')
    op.drop_column('games', 'bayes_avg_rating')
    op.drop_column('games', 'max_playtime')
    op.drop_column('games', 'min_playtime')
