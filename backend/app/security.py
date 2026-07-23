from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import secret_key
from app.db import get_db
from app.models import Band

SESSION_COOKIE = "gig_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key(), salt="gig-pipeline-session")


def create_session_token(band_id: int) -> str:
    return _serializer().dumps({"band_id": band_id})


def _session_band_id(token: str) -> int | None:
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None
    band_id = data.get("band_id")
    return band_id if isinstance(band_id, int) else None


def current_band(
    request: Request, db: Session = Depends(get_db)
) -> Band:
    """The band this request is authenticated as; 401 if the cookie is
    missing, invalid, or points at a band that no longer exists."""
    token = request.cookies.get(SESSION_COOKIE)
    band_id = _session_band_id(token) if token else None
    band = db.get(Band, band_id) if band_id is not None else None
    if band is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return band
