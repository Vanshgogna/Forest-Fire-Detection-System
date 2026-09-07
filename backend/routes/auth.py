from secrets import compare_digest

from fastapi import APIRouter, HTTPException, status

from backend.core.config import get_settings
from backend.core.security import create_access_token, create_refresh_token, decode_token
from backend.schemas.auth import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    settings = get_settings()
    if not settings.demo_login_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo login is disabled")
    valid_email = compare_digest(payload.email, settings.demo_login_email)
    valid_password = compare_digest(payload.password, settings.demo_login_password)
    if not valid_email or not valid_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    claims = {"role": "forest_officer", "scopes": ["predictions:write", "alerts:write", "reports:write"]}
    return TokenResponse(
        access_token=create_access_token(payload.email, claims),
        refresh_token=create_refresh_token(payload.email, claims),
        role="forest_officer",
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(refresh_token: str):
    payload = decode_token(refresh_token)
    if payload.get("token_type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    claims = {"role": payload.get("role", "viewer"), "scopes": payload.get("scopes", [])}
    return TokenResponse(access_token=create_access_token(payload["sub"], claims), role=claims["role"])
