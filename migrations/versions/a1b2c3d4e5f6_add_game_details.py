"""Add game detail columns for summary, rating, themes, modes, developers

Revision ID: a1b2c3d4e5f6
Revises: 8f3c4d9e2a1b
Create Date: 2026-06-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8f3c4d9e2a1b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('games_master', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('games_master', sa.Column('rating', sa.Float(), nullable=True))
    op.add_column('games_master', sa.Column('total_rating', sa.Float(), nullable=True))
    op.add_column('games_master', sa.Column('total_rating_count', sa.Integer(), nullable=True))
    op.add_column('games_master', sa.Column('themes', sa.String(500), nullable=True))
    op.add_column('games_master', sa.Column('game_modes', sa.String(255), nullable=True))
    op.add_column('games_master', sa.Column('developers', sa.String(500), nullable=True))
    op.add_column('games_master', sa.Column('publishers', sa.String(500), nullable=True))


def downgrade():
    op.drop_column('games_master', 'publishers')
    op.drop_column('games_master', 'developers')
    op.drop_column('games_master', 'game_modes')
    op.drop_column('games_master', 'themes')
    op.drop_column('games_master', 'total_rating_count')
    op.drop_column('games_master', 'total_rating')
    op.drop_column('games_master', 'rating')
    op.drop_column('games_master', 'summary')
