"""Pydantic schemas for employee registration, permissions, and profile."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

ALLOWED_COMMUNICATION_PURPOSES = [
    "Loan verification",
    "Account verification",
    "Payment reminder",
    "Fraud alert",
    "Customer support",
    "Policy renewal",
]


class EmployeeCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    employee_code: str = Field(min_length=2, max_length=100)
    designation: str = Field(min_length=2, max_length=120)
    department: str = Field(min_length=2, max_length=120)
    assigned_role: str = Field(min_length=2, max_length=120)
    allowed_purposes: list[str] = Field(default_factory=list, min_length=1)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("allowed_purposes")
    @classmethod
    def validate_purposes(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip() for v in values if v and v.strip()]
        invalid = [v for v in cleaned if v not in ALLOWED_COMMUNICATION_PURPOSES]
        if invalid:
            raise ValueError(f"Unsupported communication purposes: {', '.join(invalid)}")
        if not cleaned:
            raise ValueError("At least one allowed communication purpose is required.")
        return list(dict.fromkeys(cleaned))


class EmployeeUpdateRequest(BaseModel):
    designation: Optional[str] = Field(default=None, min_length=2, max_length=120)
    department: Optional[str] = Field(default=None, min_length=2, max_length=120)
    assigned_role: Optional[str] = Field(default=None, min_length=2, max_length=120)
    allowed_purposes: Optional[list[str]] = None
    is_active: Optional[bool] = None

    @field_validator("allowed_purposes")
    @classmethod
    def validate_purposes(cls, values: Optional[list[str]]) -> Optional[list[str]]:
        if values is None:
            return None
        cleaned = [v.strip() for v in values if v and v.strip()]
        invalid = [v for v in cleaned if v not in ALLOWED_COMMUNICATION_PURPOSES]
        if invalid:
            raise ValueError(f"Unsupported communication purposes: {', '.join(invalid)}")
        if not cleaned:
            raise ValueError("At least one allowed communication purpose is required.")
        return list(dict.fromkeys(cleaned))


class EmployeeResponse(BaseModel):
    id: int
    user_id: int
    company_id: int
    company_name: str
    company_status: str
    full_name: str
    email: EmailStr
    employee_code: str
    designation: str
    department: str
    assigned_role: str
    identity_status: str
    allowed_purposes: list[str]
    voice_enrolled: bool
    is_active: bool
    latest_enrollment: Optional[dict] = None
    created_at: datetime
