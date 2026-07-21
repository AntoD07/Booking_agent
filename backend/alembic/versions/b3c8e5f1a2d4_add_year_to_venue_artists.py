"""add year to venue_artists

Revision ID: b3c8e5f1a2d4
Revises: 8a41f60d2c55
Create Date: 2026-07-21 14:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b3c8e5f1a2d4'
down_revision = '8a41f60d2c55'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('venue_artists', sa.Column('year', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('venue_artists', 'year')
