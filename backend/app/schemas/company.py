"""Pydantic schemas for company registration and management."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class CompanyRegisterRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    business_email: EmailStr
    phone: str = Field(min_length=5, max_length=50)
    industry: str = Field(min_length=2, max_length=120)
    registration_number: str = Field(min_length=2, max_length=120)
    admin_full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class CompanyResponse(BaseModel):
    id: int
    company_name: str
    business_email: EmailStr
    phone: str
    industry: str
    registration_number: str
    verification_status: str
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyRegistrationResponse(BaseModel):
    message: str
    company: CompanyResponse
    access_token: str
    token_type: str = "bearer"


class CompanyStatusUpdateRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class CompanyRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
