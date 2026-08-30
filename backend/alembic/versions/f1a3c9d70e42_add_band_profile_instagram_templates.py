"""add band_profile instagram and editable templates

Revision ID: f1a3c9d70e42
Revises: d4f8a2c61e93
Create Date: 2026-08-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f1a3c9d70e42'
down_revision = 'd4f8a2c61e93'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('band_profile', sa.Column('instagram', sa.String(length=120), nullable=True))
    op.add_column('band_profile', sa.Column('template_fr', sa.Text(), nullable=True))
    op.add_column('band_profile', sa.Column('template_en', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('band_profile', 'template_en')
    op.drop_column('band_profile', 'template_fr')
    op.drop_column('band_profile', 'instagram')
