"""Fix categories/themes/subdomains taxonomy mislabeling

Revision ID: e7a2c58f9b16
Revises: d4a8f21c6b93
Create Date: 2026-08-16 16:00:00.000000

Fixes a taxonomy mislabeling confirmed against BGG's own wiki
(boardgamegeek.com/wiki/page/Category and /wiki/page/family):

- What this schema called "categories" (Thematic/Strategy/War/Family/CGS/
  Abstract/Party/Childrens) is BGG's rank/leaderboard classification, i.e.
  a Subdomain, not a Category.
- What this schema called "themes" is actually jvanelteren's
  boardgamecategory field, i.e. BGG's real Category taxonomy.
- A genuine BGG "Theme" is a distinct thing: the `Theme:`-prefixed group
  within BGG's Family field (e.g. "Theme: Cthulhu Mythos") — nothing in
  this schema sourced that until now.

Plain drop-and-recreate, not a rename: the pipeline truncates and reloads
these tables from CSV immediately after any schema change regardless, so
there's no in-place data worth preserving through a rename. See
docs/data/README.md.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a2c58f9b16'
down_revision: Union[str, Sequence[str], None] = 'd4a8f21c6b93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('game_categories')
    op.drop_index(op.f('ix_categories_name'), table_name='categories')
    op.drop_table('categories')

    op.drop_table('game_themes')
    op.drop_index(op.f('ix_themes_name'), table_name='themes')
    op.drop_table('themes')

    # subdomains — was "categories" (8 values: Thematic/Strategy/War/
    # Family/CGS/Abstract/Party/Childrens)
    op.create_table(
        'subdomains',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_subdomains_name'), 'subdomains', ['name'], unique=True)
    op.create_table(
        'game_subdomains',
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('subdomain_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.bgg_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subdomain_id'], ['subdomains.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('game_id', 'subdomain_id'),
    )
    op.create_index(op.f('ix_game_subdomains_subdomain_id'), 'game_subdomains', ['subdomain_id'], unique=False)

    # categories — was "themes" (jvanelteren boardgamecategory, ~86 values)
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_categories_name'), 'categories', ['name'], unique=True)
    op.create_table(
        'game_categories',
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.bgg_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('game_id', 'category_id'),
    )
    op.create_index(op.f('ix_game_categories_category_id'), 'game_categories', ['category_id'], unique=False)

    # themes — new, correctly sourced from BGG Family's "Theme:" group
    op.create_table(
        'themes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_themes_name'), 'themes', ['name'], unique=True)
    op.create_table(
        'game_themes',
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('theme_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.bgg_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['theme_id'], ['themes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('game_id', 'theme_id'),
    )
    op.create_index(op.f('ix_game_themes_theme_id'), 'game_themes', ['theme_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('game_themes')
    op.drop_index(op.f('ix_themes_name'), table_name='themes')
    op.drop_table('themes')

    op.drop_table('game_categories')
    op.drop_index(op.f('ix_categories_name'), table_name='categories')
    op.drop_table('categories')

    op.drop_table('game_subdomains')
    op.drop_index(op.f('ix_subdomains_name'), table_name='subdomains')
    op.drop_table('subdomains')

    op.create_table(
        'themes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_themes_name'), 'themes', ['name'], unique=True)
    op.create_table(
        'game_themes',
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('theme_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.bgg_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['theme_id'], ['themes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('game_id', 'theme_id'),
    )
    op.create_index(op.f('ix_game_themes_theme_id'), 'game_themes', ['theme_id'], unique=False)

    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_categories_name'), 'categories', ['name'], unique=True)
    op.create_table(
        'game_categories',
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.bgg_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('game_id', 'category_id'),
    )
    op.create_index(op.f('ix_game_categories_category_id'), 'game_categories', ['category_id'], unique=False)
