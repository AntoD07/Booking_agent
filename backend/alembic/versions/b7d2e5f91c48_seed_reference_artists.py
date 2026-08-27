"""seed reference artists for the seed band

Revision ID: b7d2e5f91c48
Revises: a1b2c3d4e5f6
Create Date: 2026-07-25 12:00:00.000000

"""
import os

from alembic import op
import sqlalchemy as sa


revision = 'b7d2e5f91c48'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

# The manouche/swing bands whose gigs are qualified leads. Seeded for the
# seed band only (other bands curate their own list); editable in-app after.
_ARTISTS = [
    "Mustaka",
    "Balo Swing",
    "Echoes of Django",
    "Die Drahtzieher",
    "Djangologists",
    "Gadjo",
    "Maria Pascual and the Kind of Gipsies",
    "Giangiacomo Rosso",
    "Amati Schmidt",
    "Harry Diplock",
]

_bands = sa.table("bands", sa.column("id", sa.Integer), sa.column("name", sa.String))
_artists = sa.table(
    "artists",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("band_id", sa.Integer),
)


def _seed_band_id(bind) -> int | None:
    name = os.environ.get("SEED_BAND_NAME") or "Gipsy Tonic"
    row = bind.execute(
        sa.select(_bands.c.id).where(sa.func.lower(_bands.c.name) == name.lower())
    ).first()
    return row[0] if row else None


def upgrade() -> None:
    bind = op.get_bind()
    band_id = _seed_band_id(bind)
    if band_id is None:
        return  # fresh install with no seed band: nothing to attach to
    for name in _ARTISTS:
        # Idempotent + case-insensitive: never duplicate one already tracked.
        exists = bind.execute(
            sa.select(_artists.c.id).where(
                _artists.c.band_id == band_id,
                sa.func.lower(_artists.c.name) == name.lower(),
            )
        ).first()
        if exists is None:
            bind.execute(_artists.insert().values(name=name, band_id=band_id))


def downgrade() -> None:
    bind = op.get_bind()
    band_id = _seed_band_id(bind)
    if band_id is None:
        return
    bind.execute(
        _artists.delete().where(
            _artists.c.band_id == band_id,
            sa.func.lower(_artists.c.name).in_([n.lower() for n in _ARTISTS]),
        )
    )
