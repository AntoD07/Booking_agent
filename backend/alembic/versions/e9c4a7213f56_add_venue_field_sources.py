"""add venues.field_sources

Revision ID: e9c4a7213f56
Revises: d8b2f0a15c37
Create Date: 2026-08-10 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e9c4a7213f56'
down_revision = 'd8b2f0a15c37'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('venues', sa.Column('field_sources', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('venues', 'field_sources')
