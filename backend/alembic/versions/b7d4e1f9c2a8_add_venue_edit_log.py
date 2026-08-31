"""add venue edit log, last-modified fields, and band members

Records who changed which venue card and when: a `venue_edits` table plus
denormalised `last_modified_by` / `last_modified_at` on venues for the card
footer. Also adds `band_profile.members` (the "who's editing" picker list) and
seeds our own band's members. All new columns are nullable — existing venues
simply start with no history until their next edit.

Revision ID: b7d4e1f9c2a8
Revises: f1a3c9d70e42
Create Date: 2026-08-31 10:00:00.000000

"""
import os

from alembic import op
import sqlalchemy as sa


revision = 'b7d4e1f9c2a8'
down_revision = 'f1a3c9d70e42'
branch_labels = None
depends_on = None

_SEED_MEMBERS = ["Anto", "Bastien", "Cris", "Sacha"]


def _seed_band_members() -> None:
    """Give our own band its member list so the picker isn't empty on day one."""
    bind = op.get_bind()
    name = os.environ.get("SEED_BAND_NAME") or "Gipsy Tonic"
    band_id = bind.execute(
        sa.text("SELECT id FROM bands WHERE lower(name) = lower(:n)"), {"n": name}
    ).scalar()
    if band_id is None:
        return
    profile = sa.table(
        "band_profile",
        sa.column("id", sa.Integer),
        sa.column("band_id", sa.Integer),
        sa.column("band_name", sa.String),
        sa.column("signature_name", sa.String),
        sa.column("members", sa.JSON),
    )
    existing = bind.execute(
        sa.text("SELECT id FROM band_profile WHERE band_id = :b"), {"b": band_id}
    ).scalar()
    if existing is None:
        op.bulk_insert(
            profile,
            [{
                "band_id": band_id,
                "band_name": name,
                "signature_name": _SEED_MEMBERS[0],
                "members": _SEED_MEMBERS,
            }],
        )
    else:
        op.execute(
            profile.update()
            .where(profile.c.id == existing)
            .values(members=_SEED_MEMBERS)
        )


def upgrade() -> None:
    op.add_column(
        'venues', sa.Column('last_modified_by', sa.String(length=100), nullable=True)
    )
    op.add_column(
        'venues',
        sa.Column('last_modified_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'venue_edits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('band_id', sa.Integer(), nullable=False),
        sa.Column('venue_id', sa.Integer(), nullable=True),
        sa.Column('venue_name', sa.String(length=200), nullable=False),
        sa.Column('editor', sa.String(length=100), nullable=True),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['band_id'], ['bands.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_venue_edits_band_id', 'venue_edits', ['band_id'])
    op.create_index('ix_venue_edits_venue_id', 'venue_edits', ['venue_id'])

    op.add_column('band_profile', sa.Column('members', sa.JSON(), nullable=True))
    _seed_band_members()


def downgrade() -> None:
    op.drop_column('band_profile', 'members')
    op.drop_index('ix_venue_edits_venue_id', table_name='venue_edits')
    op.drop_index('ix_venue_edits_band_id', table_name='venue_edits')
    op.drop_table('venue_edits')
    op.drop_column('venues', 'last_modified_at')
    op.drop_column('venues', 'last_modified_by')
