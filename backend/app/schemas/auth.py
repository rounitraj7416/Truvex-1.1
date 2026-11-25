"""Pydantic schemas for authentication and user identity."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserSummary(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    company_status: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary
