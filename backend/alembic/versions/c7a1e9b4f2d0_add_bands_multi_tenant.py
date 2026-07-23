"""add bands and scope venues/artists/drafts/runs to a band

Introduces per-band access. Creates the `bands` table, seeds one band from
SEED_BAND_NAME + APP_PASSWORD to own the data that already exists, then adds
a non-null band_id to every owner table, backfilling existing rows to that
seed band before enforcing the constraint.

Revision ID: c7a1e9b4f2d0
Revises: e6f3a9c27b41
Create Date: 2026-07-23 12:00:00.000000

"""
import os

import sqlalchemy as sa
from alembic import op

from app.passwords import hash_password

revision = 'c7a1e9b4f2d0'
down_revision = 'e6f3a9c27b41'
branch_labels = None
depends_on = None

_OWNER_TABLES = ('venues', 'artists', 'email_drafts', 'research_runs')


def _seed_band(bind) -> int:
    """Create (or reuse) the band that owns pre-existing data and return its id.

    Its password is APP_PASSWORD when set; otherwise an unusable placeholder,
    so the band exists to own rows but can't be logged into until a real
    password is set with `python -m app.register_band`.
    """
    name = os.environ.get("SEED_BAND_NAME") or "Gipsy Tonic"
    existing = bind.execute(
        sa.text("SELECT id FROM bands WHERE name = :name"), {"name": name}
    ).scalar()
    if existing is not None:
        return existing
    raw = os.environ.get("APP_PASSWORD")
    password_hash = hash_password(raw) if raw else "pbkdf2_sha256$0$$"
    bind.execute(
        sa.text(
            "INSERT INTO bands (name, password_hash, anthropic_api_key, created_at) "
            "VALUES (:name, :hash, NULL, CURRENT_TIMESTAMP)"
        ),
        {"name": name, "hash": password_hash},
    )
    return bind.execute(
        sa.text("SELECT id FROM bands WHERE name = :name"), {"name": name}
    ).scalar()


def upgrade() -> None:
    op.create_table(
        'bands',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=200), nullable=False),
        sa.Column('anthropic_api_key', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bands_name', 'bands', ['name'], unique=True)

    seed_id = _seed_band(op.get_bind())

    for table in _OWNER_TABLES:
        op.add_column(table, sa.Column('band_id', sa.Integer(), nullable=True))
        op.execute(
            sa.text(f"UPDATE {table} SET band_id = :bid").bindparams(bid=seed_id)
        )
        with op.batch_alter_table(table) as batch:
            batch.alter_column('band_id', existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(
                f'fk_{table}_band_id', 'bands', ['band_id'], ['id'], ondelete='CASCADE'
            )
            batch.create_index(f'ix_{table}_band_id', ['band_id'])


def downgrade() -> None:
    for table in _OWNER_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f'ix_{table}_band_id')
            batch.drop_constraint(f'fk_{table}_band_id', type_='foreignkey')
        op.drop_column(table, 'band_id')
    op.drop_index('ix_bands_name', table_name='bands')
    op.drop_table('bands')
