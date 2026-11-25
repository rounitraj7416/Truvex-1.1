"""Layer 1 — Business Verification service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Company


@dataclass(slots=True)
class BusinessVerificationResult:
    passed: bool
    status: str
    message: str
    company: Company | None = None
    details: dict[str, Any] = field(default_factory=dict)


def verify_business(db: Session, company_id: int) -> BusinessVerificationResult:
    """Verify that the company exists and has VERIFIED status."""
    company = db.get(Company, company_id)
    if not company:
        return BusinessVerificationResult(
            passed=False,
            status="NOT_FOUND",
            message="Associated company record does not exist.",
            company=None,
        )

    if company.verification_status != "VERIFIED":
        return BusinessVerificationResult(
            passed=False,
            status=company.verification_status,
            message=(
                f"Company '{company.company_name}' is currently {company.verification_status} "
                "and is not authorized to issue Trust IDs."
            ),
            company=company,
            details={"verification_status": company.verification_status},
        )

    return BusinessVerificationResult(
        passed=True,
        status="VERIFIED",
        message=f"Company '{company.company_name}' is verified and active.",
        company=company,
        details={
            "company_name": company.company_name,
            "industry": company.industry,
            "verification_status": company.verification_status,
        },
    )
