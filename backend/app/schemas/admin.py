"""Pydantic schemas for Platform Admin monitoring and audit logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AdminStatsResponse(BaseModel):
    total_companies: int
    pending_companies: int
    verified_companies: int
    rejected_companies: int
    suspended_companies: int
    total_employees: int
    voice_enrolled_employees: int
    issued_trust_ids: int
    active_sessions: int
    redeemed_sessions: int
    expired_sessions: int
    revoked_sessions: int
    suspicious_reports: int


class AdminSessionItem(BaseModel):
    id: int
    company_name: str
    employee_name: str
    employee_code: str
    purpose: str
    status: str
    ai_provider: str
    is_mock: bool
    issued_at: datetime
    expires_at: datetime
    redeemed_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    suspicious_report_count: int


class AdminSuspiciousReportItem(BaseModel):
    id: int
    communication_session_id: int
    company_name: str
    employee_name: str
    purpose: str
    reason: str
    description: Optional[str] = None
    status: str
    created_at: datetime


class AdminAuditLogItem(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_role: str
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None
    timestamp: datetime


class ReportStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(OPEN|REVIEWED|CONFIRMED_SUSPICIOUS|DISMISSED)$")
