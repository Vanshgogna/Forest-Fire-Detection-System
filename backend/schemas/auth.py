from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

STRICT_SCHEMA_CONFIG = ConfigDict(extra="forbid")


class LoginRequest(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    role: str


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    model_config = ConfigDict(from_attributes=True)
