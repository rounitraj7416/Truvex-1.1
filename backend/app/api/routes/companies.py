"""Company registration and company admin self-service routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.dependencies import require_roles
from app.core.security import create_access_token, hash_password
from app.db.database import get_db
from app.db.models import AuditLog, CommunicationSession, Company, Employee, SuspiciousReport, User
from app.schemas.company import (
    CompanyRegisterRequest,
    CompanyRegistrationResponse,
    CompanyResponse,
)
from app.services.audit_service import record_audit_event
from app.services.session_service import revoke_communication_session

router = APIRouter(prefix="/api/companies", tags=["Companies"])


@router.post(
    "/register",
    response_model=CompanyRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_company(
    payload: CompanyRegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Register a new company in PENDING verification status with a company_admin user."""
    email_norm = payload.business_email.strip().lower()
    reg_norm = payload.registration_number.strip().upper()

    if db.scalar(select(Company).where(Company.business_email == email_norm)) or db.scalar(
        select(User).where(User.email == email_norm)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A company or user with this business email already exists.",
        )

    if db.scalar(select(Company).where(Company.registration_number == reg_norm)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A company with this business registration identifier already exists.",
        )

    company = Company(
        company_name=payload.company_name.strip(),
        business_email=email_norm,
        phone=payload.phone.strip(),
        industry=payload.industry.strip(),
        registration_number=reg_norm,
        verification_status="PENDING",
    )
    db.add(company)
    db.flush()

    admin_name = (
        payload.admin_full_name.strip()
        if payload.admin_full_name
        else f"{company.company_name} Admin"
    )
    user = User(
        email=email_norm,
        password_hash=hash_password(payload.password),
        full_name=admin_name,
        role="company_admin",
        company_id=company.id,
        is_active=True,
    )
    db.add(user)
    db.flush()

    record_audit_event(
        db,
        actor_id=user.id,
        actor_role="company_admin",
        action="COMPANY_REGISTERED",
        entity_type="company",
        entity_id=company.id,
        metadata={
            "company_name": company.company_name,
            "industry": company.industry,
            "registration_number": company.registration_number,
        },
    )
    db.commit()
    db.refresh(company)

    token = create_access_token(
        user_id=user.id, role=user.role, company_id=company.id
    )
    settings = get_settings()
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )

    return CompanyRegistrationResponse(
        message="Company registered successfully. Status is PENDING platform administrator approval.",
        company=CompanyResponse.model_validate(company),
        access_token=token,
    )


@router.get("/me")
def get_my_company(
    current_user: User = Depends(require_roles("company_admin", "employee")),
    db: Session = Depends(get_db),
):
    """Get the authenticated user's company profile and status history."""
    if not current_user.company_id:
        raise HTTPException(status_code=404, detail="No company associated with account.")

    company = db.get(Company, current_user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    history = db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "company", AuditLog.entity_id == company.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(25)
    ).all()

    return {
        "company": CompanyResponse.model_validate(company),
        "history": [
            {
                "action": h.action,
                "actor_role": h.actor_role,
                "metadata": h.metadata_json,
                "timestamp": h.timestamp,
            }
            for h in history
        ],
    }


@router.get("/me/sessions")
def list_company_sessions(
    current_user: User = Depends(require_roles("company_admin")),
    db: Session = Depends(get_db),
):
    """List communication sessions belonging strictly to the company_admin's company."""
    sessions = db.scalars(
        select(CommunicationSession)
        .options(joinedload(CommunicationSession.employee).joinedload(Employee.user))
        .where(CommunicationSession.company_id == current_user.company_id)
        .order_by(CommunicationSession.issued_at.desc())
        .limit(50)
    ).all()

    items = []
    for s in sessions:
        report_count = db.scalar(
            select(func.count(SuspiciousReport.id)).where(
                SuspiciousReport.communication_session_id == s.id
            )
        ) or 0
        items.append(
            {
                "id": s.id,
                "employee_name": s.employee.user.full_name,
                "employee_code": s.employee.employee_code,
                "purpose": s.purpose,
                "status": s.status,
                "ai_provider": s.ai_provider,
                "is_mock": s.is_mock,
                "issued_at": s.issued_at,
                "expires_at": s.expires_at,
                "redeemed_at": s.redeemed_at,
                "revoked_at": s.revoked_at,
                "suspicious_report_count": report_count,
            }
        )
    return {"sessions": items}


@router.post("/me/sessions/{session_id}/revoke")
def revoke_company_session(
    session_id: int,
    current_user: User = Depends(require_roles("company_admin")),
    db: Session = Depends(get_db),
):
    """Allow a company admin to revoke one of their own company's Trust ID sessions."""
    comm = db.get(CommunicationSession, session_id)
    if not comm or comm.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Communication session not found.")

    updated = revoke_communication_session(
        db,
        session_id=comm.id,
        actor_id=current_user.id,
        actor_role=current_user.role,
        reason="Revoked by company administrator",
    )
    return {"message": "Session revoked.", "status": updated.status if updated else "REVOKED"}
