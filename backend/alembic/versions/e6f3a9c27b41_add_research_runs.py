"""add research runs, findings, and venues.last_researched

Revision ID: e6f3a9c27b41
Revises: d5e2a7c93b18
Create Date: 2026-07-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e6f3a9c27b41'
down_revision = 'd5e2a7c93b18'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'venues',
        sa.Column('last_researched', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'research_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('venues_checked', sa.Integer(), nullable=False),
        sa.Column('fields_filled', sa.Integer(), nullable=False),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'research_findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('venue_id', sa.Integer(), nullable=True),
        sa.Column('venue_name', sa.String(length=200), nullable=False),
        sa.Column('field', sa.String(length=50), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=False),
        sa.Column('confidence', sa.String(length=10), nullable=False),
        sa.Column('source', sa.String(length=500), nullable=True),
        sa.Column('applied', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['research_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('research_findings')
    op.drop_table('research_runs')
    op.drop_column('venues', 'last_researched')
