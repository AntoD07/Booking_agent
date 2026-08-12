"""add email_drafts.source

Revision ID: d8b2f0a15c37
Revises: c7a1e9f4b620
Create Date: 2026-08-10 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd8b2f0a15c37'
down_revision = 'c7a1e9f4b620'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'email_drafts', sa.Column('source', sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('email_drafts', 'source')
