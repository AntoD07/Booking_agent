import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import app_password, cookie_secure
from app.db import get_db
from app.models import Band
from app.passwords import hash_password, verify_password
from app.schemas import (
    LoginRequest,
    RegisterBandOut,
    RegisterBandRequest,
    SessionOut,
)
from app.security import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_token,
    current_band,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    # Case-insensitive band name so "Gipsy Tonic" and "gipsy tonic" both work.
    band = db.scalar(
        select(Band).where(func.lower(Band.name) == payload.band_name.strip().lower())
    )
    # Verify even when the band is unknown, against a dummy hash, so a wrong
    # band name and a wrong password take the same time to reject.
    stored = band.password_hash if band else "pbkdf2_sha256$240000$00$00"
    if not verify_password(payload.password, stored) or band is None:
        raise HTTPException(status_code=401, detail="Wrong band name or password")
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(band.id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
    )
    return {"ok": True}


@router.post("/register-band", response_model=RegisterBandOut)
def register_band(
    payload: RegisterBandRequest, db: Session = Depends(get_db)
) -> RegisterBandOut:
    """Create a band, or reset an existing band's password.

    Gated by the owner secret (APP_PASSWORD) so it can be used from the login
    screen without shell access — the free hosting tier has no shell. Re-using
    an existing name (case-insensitive) resets that band's password."""
    expected = app_password()
    if expected is None:
        raise HTTPException(status_code=503, detail="APP_PASSWORD is not configured")
    if not secrets.compare_digest(payload.admin_password.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Wrong owner password")
    name = payload.band_name.strip()
    band = db.scalar(select(Band).where(func.lower(Band.name) == name.lower()))
    created = band is None
    if band is None:
        band = Band(name=name, password_hash=hash_password(payload.password))
        db.add(band)
    else:
        band.password_hash = hash_password(payload.password)
    db.commit()
    return RegisterBandOut(band_name=name, created=created)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me", response_model=SessionOut)
def me(band: Band = Depends(current_band)) -> SessionOut:
    return SessionOut(band_name=band.name)
