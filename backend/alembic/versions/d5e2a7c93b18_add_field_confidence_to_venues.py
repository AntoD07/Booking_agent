"""add field_confidence to venues

Revision ID: d5e2a7c93b18
Revises: b3c8e5f1a2d4
Create Date: 2026-07-21 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd5e2a7c93b18'
down_revision = 'b3c8e5f1a2d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('venues', sa.Column('field_confidence', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('venues', 'field_confidence')
