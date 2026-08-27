"""campaign start: reset seed band's pipeline

One-shot cleanup before the 2027 campaign begins: every one of the seed
band's venues returns to Discovered, and its test-era email drafts are
deleted. Other bands' pipelines are untouched.

Revision ID: d4f8a2c61e93
Revises: b7d2e5f91c48
Create Date: 2026-07-27 10:00:00.000000

"""
import os

from alembic import op
import sqlalchemy as sa


revision = 'd4f8a2c61e93'
down_revision = 'b7d2e5f91c48'
branch_labels = None
depends_on = None

_bands = sa.table("bands", sa.column("id", sa.Integer), sa.column("name", sa.String))
_venues = sa.table(
    "venues",
    sa.column("id", sa.Integer),
    sa.column("status", sa.String),
    sa.column("band_id", sa.Integer),
)
_drafts = sa.table("email_drafts", sa.column("band_id", sa.Integer))


def upgrade() -> None:
    bind = op.get_bind()
    name = os.environ.get("SEED_BAND_NAME") or "Gipsy Tonic"
    row = bind.execute(
        sa.select(_bands.c.id).where(sa.func.lower(_bands.c.name) == name.lower())
    ).first()
    if row is None:
        return  # fresh install: nothing to reset
    band_id = row[0]
    bind.execute(
        _venues.update()
        .where(_venues.c.band_id == band_id)
        .values(status="discovered")
    )
    bind.execute(_drafts.delete().where(_drafts.c.band_id == band_id))


def downgrade() -> None:
    # Statuses and deleted drafts cannot be restored; nothing to undo.
    pass
