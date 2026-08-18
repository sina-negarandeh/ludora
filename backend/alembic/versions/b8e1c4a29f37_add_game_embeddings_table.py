"""add game_embeddings table, drop games embedding columns

Revision ID: b8e1c4a29f37
Revises: 7504c1be2bde
Create Date: 2026-08-17 18:30:00.000000

games.embedding was a fixed-dimension VECTOR(384) column tied to one
embedding model at a time — swapping models (or comparing two side by
side) meant either a destructive column migration or overwriting the
only copy on every rerun, with no history. game_embeddings holds one row
per (game, model) instead, so multiple models' vectors can coexist for
comparison; embedding is left unsized (no fixed dim) since different
models produce different dimensions and each query already filters to
one model before computing distance.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'b8e1c4a29f37'
down_revision: Union[str, Sequence[str], None] = '7504c1be2bde'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'game_embeddings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.bgg_id', ondelete='CASCADE'), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('dimension', sa.Integer(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('game_id', 'model', name='uq_game_embeddings_game_id_model'),
    )
    op.create_index('ix_game_embeddings_game_id', 'game_embeddings', ['game_id'])
    op.create_index('ix_game_embeddings_model', 'game_embeddings', ['model'])

    op.drop_column('games', 'embedding')
    op.drop_column('games', 'embedding_model')
    op.drop_column('games', 'embedding_updated_at')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('games', sa.Column('embedding_updated_at', sa.DateTime(), nullable=True))
    op.add_column('games', sa.Column('embedding_model', sa.String(), nullable=True))
    op.add_column('games', sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True))

    op.drop_index('ix_game_embeddings_model', table_name='game_embeddings')
    op.drop_index('ix_game_embeddings_game_id', table_name='game_embeddings')
    op.drop_table('game_embeddings')
