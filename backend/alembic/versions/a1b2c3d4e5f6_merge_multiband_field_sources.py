"""merge multi-band and venue field_sources heads

Two migrations independently descend from d8b2f0a15c37: the multi-band
scoping (c7a1e9b4f2d0) and venues.field_sources (e9c4a7213f56). They touch
different columns and don't conflict; this merge joins them into one head so
`alembic upgrade head` has a single target.

Revision ID: a1b2c3d4e5f6
Revises: c7a1e9b4f2d0, e9c4a7213f56
Create Date: 2026-08-12 14:00:00.000000

"""

revision = 'a1b2c3d4e5f6'
down_revision = ('c7a1e9b4f2d0', 'e9c4a7213f56')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
