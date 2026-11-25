"""Layer 2 — Employee Identity Verification service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Employee, User


@dataclass(slots=True)
class EmployeeVerificationResult:
    passed: bool
    status: str
    message: str
    employee: Employee | None = None
    details: dict[str, Any] = field(default_factory=dict)


def verify_employee_identity(db: Session, user: User) -> EmployeeVerificationResult:
    """
    Verify authenticated employee account, company association, active status,
    and company-attested identity status.
    """
    if user.role != "employee":
        return EmployeeVerificationResult(
            passed=False,
            status="INVALID_ROLE",
            message="Only employee accounts may undergo employee communication verification.",
        )

    if not user.is_active:
        return EmployeeVerificationResult(
            passed=False,
            status="USER_INACTIVE",
            message="Employee user account is deactivated.",
        )

    employee = db.scalar(select(Employee).where(Employee.user_id == user.id))
    if not employee:
        return EmployeeVerificationResult(
            passed=False,
            status="PROFILE_MISSING",
            message="Employee profile record not found.",
        )

    if user.company_id is None or employee.company_id != user.company_id:
        return EmployeeVerificationResult(
            passed=False,
            status="COMPANY_MISMATCH",
            message="Employee company association could not be verified.",
            employee=employee,
        )

    if employee.identity_status != "COMPANY_ATTESTED":
        return EmployeeVerificationResult(
            passed=False,
            status=employee.identity_status,
            message="Employee identity attestation is not active.",
            employee=employee,
        )

    if not employee.voice_enrolled:
        return EmployeeVerificationResult(
            passed=False,
            status="VOICE_NOT_ENROLLED",
            message="Employee must complete voice enrollment before pre-call verification.",
            employee=employee,
        )

    return EmployeeVerificationResult(
        passed=True,
        status="COMPANY_ATTESTED",
        message="Authenticated employee identity attested by employer.",
        employee=employee,
        details={
            "employee_code": employee.employee_code,
            "designation": employee.designation,
            "department": employee.department,
            "identity_status": employee.identity_status,
        },
    )
