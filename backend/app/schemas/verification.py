"""Pydantic schemas for verification, Trust ID issuance, public verification, and reporting."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

SUSPICIOUS_REASONS = [
    "Employee identity seems incorrect",
    "Suspicious voice",
    "Unexpected communication purpose",
    "I did not expect this call",
    "Other",
]


class LayerResultSchema(BaseModel):
    layer: str
    passed: bool
    status: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class TrustIDIssueResponse(BaseModel):
    trust_id: Optional[str] = None
    issued: bool
    overall_status: str
    purpose: str
    reference_note: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    ai_provider: str
    is_mock: bool
    mock_notice: Optional[str] = None
    layer_results: list[LayerResultSchema]


class VoiceEnrollmentResponse(BaseModel):
    enrolled: bool
    status: str
    provider: str
    is_mock: bool
    mock_notice: Optional[str] = None
    enrolled_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class PublicVerifyRequest(BaseModel):
    trust_id: str = Field(min_length=6, max_length=64)


class PublicCompanyInfo(BaseModel):
    company_name: str
    verification_status: str
    industry: str
    verification_indicator: str


class PublicEmployeeInfo(BaseModel):
    full_name: str
    designation: str
    department: str
    authorization_status: str
    company_association: str


class PublicAIAssessment(BaseModel):
    voice_verification_decision: str
    voice_match_score: Optional[float] = None
    deepfake_decision: str
    deepfake_risk_score: Optional[float] = None
    assessment_timestamp: datetime
    provider_name: str
    is_mock: bool
    mock_notice: Optional[str] = None


class PublicCommunicationInfo(BaseModel):
    purpose: str
    reference_note: Optional[str] = None
    issued_at: datetime
    expires_at: datetime
    redeemed_at: Optional[datetime] = None
    session_validity: str


class PublicVerificationResponse(BaseModel):
    overall_status: str  # Verified | Suspicious | Expired | Invalid
    status_explanation: str
    suspicious_reported: bool = False
    customer_session_active: bool = False
    company: Optional[PublicCompanyInfo] = None
    employee: Optional[PublicEmployeeInfo] = None
    ai_assessment: Optional[PublicAIAssessment] = None
    communication: Optional[PublicCommunicationInfo] = None


class SuspiciousReportRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned not in SUSPICIOUS_REASONS:
            raise ValueError(f"Invalid reason. Must be one of: {', '.join(SUSPICIOUS_REASONS)}")
        return cleaned


class SuspiciousReportResponse(BaseModel):
    reported: bool
    message: str
    reason: str
    created_at: datetime
    overall_status: str
