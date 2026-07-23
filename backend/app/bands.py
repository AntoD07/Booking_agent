"""Helpers for the band that owns pre-multi-band data.

The Alembic migration creates this band; these helpers let the deploy-time
Notion import and the local seed script find (or, in a fresh dev database,
create) it so the rows they add have an owner.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import app_password, seed_band_name
from app.models import Band
from app.passwords import hash_password


def get_or_create_seed_band(db: Session) -> Band:
    name = seed_band_name()
    band = db.scalar(select(Band).where(func.lower(Band.name) == name.lower()))
    if band is None:
        raw = app_password()
        band = Band(
            name=name,
            # Unusable placeholder when APP_PASSWORD isn't set; register a real
            # password later with `python -m app.register_band`.
            password_hash=hash_password(raw) if raw else "pbkdf2_sha256$0$$",
        )
        db.add(band)
        db.commit()
        db.refresh(band)
    return band
