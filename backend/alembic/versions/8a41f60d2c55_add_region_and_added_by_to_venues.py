"""add region and added_by to venues

Revision ID: 8a41f60d2c55
Revises: 1ec413cdf5e8
Create Date: 2026-07-21 14:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '8a41f60d2c55'
down_revision = '1ec413cdf5e8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('venues', sa.Column('region', sa.String(length=100), nullable=True))
    op.add_column('venues', sa.Column('added_by', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('venues', 'added_by')
    op.drop_column('venues', 'region')
