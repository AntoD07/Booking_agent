"""add band_profile

Revision ID: c7a1e9f4b620
Revises: e6f3a9c27b41
Create Date: 2026-08-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c7a1e9f4b620'
down_revision = 'e6f3a9c27b41'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'band_profile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('band_name', sa.String(length=120), nullable=False),
        sa.Column('signature_name', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=60), nullable=True),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('website', sa.String(length=200), nullable=True),
        sa.Column('video1_url', sa.String(length=500), nullable=True),
        sa.Column('video2_url', sa.String(length=500), nullable=True),
        sa.Column('epk_url', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('band_profile')
