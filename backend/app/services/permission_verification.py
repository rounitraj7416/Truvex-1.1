"""Layer 4 — Authority and Permission Verification service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.db.models import Employee
from app.schemas.employee import ALLOWED_COMMUNICATION_PURPOSES


@dataclass(slots=True)
class PermissionVerificationResult:
    passed: bool
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def verify_communication_permission(
    employee: Employee,
    requested_purpose: str,
) -> PermissionVerificationResult:
    """Verify the requested purpose is valid and explicitly assigned to the employee."""
    purpose = requested_purpose.strip()
    if purpose not in ALLOWED_COMMUNICATION_PURPOSES:
        return PermissionVerificationResult(
            passed=False,
            status="UNSUPPORTED_PURPOSE",
            message=f"'{purpose}' is not a supported communication purpose.",
            details={"requested_purpose": purpose},
        )

    assigned = list(employee.allowed_purposes or [])
    if purpose not in assigned:
        return PermissionVerificationResult(
            passed=False,
            status="PURPOSE_NOT_AUTHORIZED",
            message=(
                f"Employee is not authorized to initiate '{purpose}' communications. "
                f"Assigned purposes: {', '.join(assigned) or 'None'}."
            ),
            details={"requested_purpose": purpose, "assigned_purposes": assigned},
        )

    return PermissionVerificationResult(
        passed=True,
        status="AUTHORIZED",
        message=f"Employee is authorized for '{purpose}'.",
        details={"purpose": purpose},
    )
