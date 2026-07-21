from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import secret_key

SESSION_COOKIE = "gig_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key(), salt="gig-pipeline-session")


def create_session_token() -> str:
    return _serializer().dumps({"authenticated": True})


def verify_session_token(token: str) -> bool:
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return False
    return data.get("authenticated") is True


def require_session(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token or not verify_session_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
