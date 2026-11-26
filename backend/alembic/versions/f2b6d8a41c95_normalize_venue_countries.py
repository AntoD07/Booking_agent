"""normalize venue countries to one canonical spelling

The country column is free text, so the same country appears under several
spellings ("Suisse" and "Switzerland") and the board filter shows twins.
New writes are normalized in the API schemas (app.countries); this one-shot
pass folds the rows already stored, across all bands.

Revision ID: f2b6d8a41c95
Revises: b7d4e1f9c2a8
Create Date: 2026-09-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

from app.countries import normalize_country


revision = 'f2b6d8a41c95'
down_revision = 'b7d4e1f9c2a8'
branch_labels = None
depends_on = None

_venues = sa.table(
    "venues",
    sa.column("id", sa.Integer),
    sa.column("country", sa.String),
)


def upgrade() -> None:
    bind = op.get_bind()
    for venue_id, country in bind.execute(
        sa.select(_venues.c.id, _venues.c.country).where(
            _venues.c.country.is_not(None)
        )
    ):
        canonical = normalize_country(country)
        if canonical != country:
            bind.execute(
                sa.update(_venues)
                .where(_venues.c.id == venue_id)
                .values(country=canonical)
            )


def downgrade() -> None:
    # The original spellings are gone; there is nothing meaningful to restore.
    pass
