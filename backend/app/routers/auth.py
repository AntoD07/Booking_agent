import secrets

from fastapi import APIRouter, Depends, HTTPException, Response

from app.config import app_password, cookie_secure
from app.schemas import LoginRequest
from app.security import SESSION_COOKIE, SESSION_MAX_AGE, create_session_token, require_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, response: Response) -> dict:
    expected = app_password()
    if expected is None:
        raise HTTPException(status_code=503, detail="APP_PASSWORD is not configured")
    if not secrets.compare_digest(payload.password.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Wrong password")
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me", dependencies=[Depends(require_session)])
def me() -> dict:
    return {"authenticated": True}
