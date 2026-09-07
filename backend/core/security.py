from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from backend.core.config import get_settings

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Principal(BaseModel):
    subject: str
    role: str = "viewer"
    scopes: list[str] = Field(default_factory=list)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": subject, "exp": expire, "token_type": "access", **(claims or {})}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    payload = {"sub": subject, "exp": expire, "token_type": "refresh", **(claims or {})}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc


def require_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    return decode_token(token)


def get_current_principal(token: str = Depends(oauth2_scheme)) -> Principal:
    payload = decode_token(token)
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    return Principal(subject=subject, role=payload.get("role", "viewer"), scopes=payload.get("scopes", []))


class RoleChecker:
    def __init__(self, allowed_roles: set[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in self.allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return principal


require_admin = RoleChecker({"admin"})
require_operator = RoleChecker({"admin", "government_officer", "forest_officer"})
require_researcher = RoleChecker({"admin", "government_officer", "forest_officer", "researcher"})
