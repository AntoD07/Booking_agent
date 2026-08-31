import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import app_password, cookie_secure
from app.db import get_db
from app.models import Band, BandProfile, Venue, VenueEdit
from app.passwords import hash_password, verify_password
from app.schemas import (
    EditorSet,
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
    current_editor,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, band_id: int, editor: str | None) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(band_id, editor),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
    )


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
    _set_session_cookie(response, band.id, editor=None)
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
def me(
    band: Band = Depends(current_band), editor: str | None = Depends(current_editor)
) -> SessionOut:
    return SessionOut(band_name=band.name, editor=editor)


@router.post("/editor", response_model=SessionOut)
def set_editor(
    payload: EditorSet,
    response: Response,
    band: Band = Depends(current_band),
) -> SessionOut:
    """Choose which bandmate this device edits under. Re-issues the session
    cookie so subsequent edits are attributed to this name."""
    name = payload.name.strip()
    _set_session_cookie(response, band.id, editor=name)
    return SessionOut(band_name=band.name, editor=name)


@router.get("/editors", response_model=list[str])
def list_editors(
    db: Session = Depends(get_db), band: Band = Depends(current_band)
) -> list[str]:
    """Names for the "who's editing" picker: the band's member list first (in
    the order set on the profile), then any other names seen in past edits."""
    ordered: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        if name and name != "Claude" and name.lower() not in seen:
            seen.add(name.lower())
            ordered.append(name)

    profile = db.scalar(
        select(BandProfile).where(BandProfile.band_id == band.id)
    )
    for member in (profile.members if profile else None) or []:
        add(member)
    for value in db.scalars(
        select(VenueEdit.editor)
        .where(VenueEdit.band_id == band.id, VenueEdit.editor.is_not(None))
        .distinct()
    ):
        add(value)
    for value in db.scalars(
        select(Venue.last_modified_by)
        .where(Venue.band_id == band.id, Venue.last_modified_by.is_not(None))
        .distinct()
    ):
        add(value)
    return ordered
