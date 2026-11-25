"""Platform Administrator routes: company approvals, monitoring, reports, and audit logs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import require_roles
from app.core.security import utc_now
from app.db.database import get_db
from app.db.models import (
    AuditLog,
    CommunicationSession,
    Company,
    Employee,
    SuspiciousReport,
    User,
)
from app.schemas.admin import (
    AdminAuditLogItem,
    AdminSessionItem,
    AdminStatsResponse,
    AdminSuspiciousReportItem,
    ReportStatusUpdateRequest,
)
from app.schemas.company import (
    CompanyRejectRequest,
    CompanyResponse,
    CompanyStatusUpdateRequest,
)
from app.services.audit_service import record_audit_event
from app.services.session_service import revoke_communication_session

router = APIRouter(
    prefix="/api/admin",
    tags=["Platform Admin"],
    dependencies=[Depends(require_roles("platform_admin"))],
)


@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(db: Session = Depends(get_db)):
    """Compute real-time platform statistics directly from SQLite."""
    now = utc_now()
    total_companies = db.scalar(select(func.count(Company.id))) or 0
    pending_companies = (
        db.scalar(
            select(func.count(Company.id)).where(Company.verification_status == "PENDING")
        )
        or 0
    )
    verified_companies = (
        db.scalar(
            select(func.count(Company.id)).where(Company.verification_status == "VERIFIED")
        )
        or 0
    )
    rejected_companies = (
        db.scalar(
            select(func.count(Company.id)).where(Company.verification_status == "REJECTED")
        )
        or 0
    )
    suspended_companies = (
        db.scalar(
            select(func.count(Company.id)).where(Company.verification_status == "SUSPENDED")
        )
        or 0
    )
    total_employees = db.scalar(select(func.count(Employee.id))) or 0
    voice_enrolled_employees = (
        db.scalar(select(func.count(Employee.id)).where(Employee.voice_enrolled.is_(True)))
        or 0
    )
    issued_trust_ids = db.scalar(select(func.count(CommunicationSession.id))) or 0
    active_sessions = (
        db.scalar(
            select(func.count(CommunicationSession.id)).where(
                CommunicationSession.status == "ACTIVE",
                CommunicationSession.expires_at > now,
                CommunicationSession.revoked_at.is_(None),
            )
        )
        or 0
    )
    redeemed_sessions = (
        db.scalar(
            select(func.count(CommunicationSession.id)).where(
                CommunicationSession.status == "REDEEMED"
            )
        )
        or 0
    )
    expired_sessions = (
        db.scalar(
            select(func.count(CommunicationSession.id)).where(
                (CommunicationSession.status == "EXPIRED")
                | (
                    (CommunicationSession.status == "ACTIVE")
                    & (CommunicationSession.expires_at <= now)
                )
            )
        )
        or 0
    )
    revoked_sessions = (
        db.scalar(
            select(func.count(CommunicationSession.id)).where(
                CommunicationSession.status == "REVOKED"
            )
        )
        or 0
    )
    suspicious_reports = db.scalar(select(func.count(SuspiciousReport.id))) or 0

    return AdminStatsResponse(
        total_companies=total_companies,
        pending_companies=pending_companies,
        verified_companies=verified_companies,
        rejected_companies=rejected_companies,
        suspended_companies=suspended_companies,
        total_employees=total_employees,
        voice_enrolled_employees=voice_enrolled_employees,
        issued_trust_ids=issued_trust_ids,
        active_sessions=active_sessions,
        redeemed_sessions=redeemed_sessions,
        expired_sessions=expired_sessions,
        revoked_sessions=revoked_sessions,
        suspicious_reports=suspicious_reports,
    )


@router.get("/companies", response_model=list[CompanyResponse])
def list_companies(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List registered companies with optional verification_status filter."""
    stmt = select(Company).order_by(Company.created_at.desc())
    if status:
        stmt = stmt.where(Company.verification_status == status.strip().upper())
    companies = db.scalars(stmt).all()
    return [CompanyResponse.model_validate(c) for c in companies]


@router.get("/companies/{company_id}/history")
def get_company_history(company_id: int, db: Session = Depends(get_db)):
    """Inspect a company and its full approval/status audit history."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "company", AuditLog.entity_id == company.id)
        .order_by(AuditLog.timestamp.desc())
    ).all()
    return {
        "company": CompanyResponse.model_validate(company),
        "history": [
            {
                "id": l.id,
                "actor_id": l.actor_id,
                "actor_role": l.actor_role,
                "action": l.action,
                "metadata": l.metadata_json,
                "timestamp": l.timestamp,
            }
            for l in logs
        ],
    }


@router.post("/companies/{company_id}/approve", response_model=CompanyResponse)
def approve_company(
    company_id: int,
    payload: Optional[CompanyStatusUpdateRequest] = None,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    """Approve a pending company, setting status to VERIFIED."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    now = utc_now()
    previous_status = company.verification_status
    company.verification_status = "VERIFIED"
    company.verified_at = now
    company.verified_by_id = current_user.id
    company.rejection_reason = None
    company.updated_at = now

    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="COMPANY_APPROVED",
        entity_type="company",
        entity_id=company.id,
        metadata={
            "previous_status": previous_status,
            "new_status": "VERIFIED",
            "note": payload.reason if payload else None,
        },
    )
    db.commit()
    db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.post("/companies/{company_id}/reject", response_model=CompanyResponse)
def reject_company(
    company_id: int,
    payload: CompanyRejectRequest,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    """Reject a company registration with a required reason."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    now = utc_now()
    previous_status = company.verification_status
    company.verification_status = "REJECTED"
    company.rejection_reason = payload.reason.strip()
    company.verified_by_id = current_user.id
    company.updated_at = now

    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="COMPANY_REJECTED",
        entity_type="company",
        entity_id=company.id,
        metadata={
            "previous_status": previous_status,
            "new_status": "REJECTED",
            "reason": company.rejection_reason,
        },
    )
    db.commit()
    db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.post("/companies/{company_id}/suspend", response_model=CompanyResponse)
def suspend_company(
    company_id: int,
    payload: Optional[CompanyStatusUpdateRequest] = None,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    """Suspend an approved company."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    now = utc_now()
    previous_status = company.verification_status
    company.verification_status = "SUSPENDED"
    company.rejection_reason = (
        payload.reason.strip() if payload and payload.reason else "Suspended by platform admin"
    )
    company.updated_at = now

    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="COMPANY_SUSPENDED",
        entity_type="company",
        entity_id=company.id,
        metadata={
            "previous_status": previous_status,
            "new_status": "SUSPENDED",
            "reason": company.rejection_reason,
        },
    )
    db.commit()
    db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.post("/companies/{company_id}/reactivate", response_model=CompanyResponse)
def reactivate_company(
    company_id: int,
    payload: Optional[CompanyStatusUpdateRequest] = None,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    """Reactivate a suspended company back to VERIFIED status."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    now = utc_now()
    previous_status = company.verification_status
    company.verification_status = "VERIFIED"
    company.verified_at = now
    company.verified_by_id = current_user.id
    company.rejection_reason = None
    company.updated_at = now

    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="COMPANY_REACTIVATED",
        entity_type="company",
        entity_id=company.id,
        metadata={
            "previous_status": previous_status,
            "new_status": "VERIFIED",
            "note": payload.reason if payload else None,
        },
    )
    db.commit()
    db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.get("/employees")
def list_all_employees(db: Session = Depends(get_db)):
    """List all employees across registered companies."""
    employees = db.scalars(
        select(Employee)
        .options(joinedload(Employee.user), joinedload(Employee.company))
        .order_by(Employee.created_at.desc())
        .limit(100)
    ).all()
    return {
        "employees": [
            {
                "id": e.id,
                "full_name": e.user.full_name,
                "email": e.user.email,
                "employee_code": e.employee_code,
                "company_name": e.company.company_name,
                "company_status": e.company.verification_status,
                "designation": e.designation,
                "department": e.department,
                "assigned_role": e.assigned_role,
                "allowed_purposes": e.allowed_purposes,
                "voice_enrolled": e.voice_enrolled,
                "is_active": e.user.is_active,
                "created_at": e.created_at,
            }
            for e in employees
        ]
    }


@router.get("/sessions", response_model=list[AdminSessionItem])
def list_all_sessions(db: Session = Depends(get_db)):
    """List recent Trust ID communication sessions across the platform."""
    sessions = db.scalars(
        select(CommunicationSession)
        .options(
            joinedload(CommunicationSession.company),
            joinedload(CommunicationSession.employee).joinedload(Employee.user),
        )
        .order_by(CommunicationSession.issued_at.desc())
        .limit(100)
    ).all()
    now = utc_now()
    items: list[AdminSessionItem] = []
    for s in sessions:
        report_count = (
            db.scalar(
                select(func.count(SuspiciousReport.id)).where(
                    SuspiciousReport.communication_session_id == s.id
                )
            )
            or 0
        )
        effective_status = s.status
        if s.status == "ACTIVE" and s.expires_at <= now:
            effective_status = "EXPIRED"
        items.append(
            AdminSessionItem(
                id=s.id,
                company_name=s.company.company_name,
                employee_name=s.employee.user.full_name,
                employee_code=s.employee.employee_code,
                purpose=s.purpose,
                status=effective_status,
                ai_provider=s.ai_provider,
                is_mock=s.is_mock,
                issued_at=s.issued_at,
                expires_at=s.expires_at,
                redeemed_at=s.redeemed_at,
                revoked_at=s.revoked_at,
                suspicious_report_count=report_count,
            )
        )
    return items


@router.post("/sessions/{session_id}/revoke")
def admin_revoke_session(
    session_id: int,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    """Revoke any communication session."""
    comm = revoke_communication_session(
        db,
        session_id=session_id,
        actor_id=current_user.id,
        actor_role=current_user.role,
        reason="Revoked by platform administrator",
    )
    if not comm:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"message": "Communication session revoked.", "status": comm.status}


@router.get("/reports", response_model=list[AdminSuspiciousReportItem])
def list_suspicious_reports(db: Session = Depends(get_db)):
    """List customer-submitted suspicious communication reports."""
    reports = db.scalars(
        select(SuspiciousReport)
        .options(
            joinedload(SuspiciousReport.communication_session).joinedload(
                CommunicationSession.company
            ),
            joinedload(SuspiciousReport.communication_session)
            .joinedload(CommunicationSession.employee)
            .joinedload(Employee.user),
        )
        .order_by(SuspiciousReport.created_at.desc())
        .limit(100)
    ).all()
    return [
        AdminSuspiciousReportItem(
            id=r.id,
            communication_session_id=r.communication_session_id,
            company_name=r.communication_session.company.company_name,
            employee_name=r.communication_session.employee.user.full_name,
            purpose=r.communication_session.purpose,
            reason=r.reason,
            description=r.description,
            status=r.status,
            created_at=r.created_at,
        )
        for r in reports
    ]


@router.patch("/reports/{report_id}")
def update_report_status(
    report_id: int,
    payload: ReportStatusUpdateRequest,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    """Update triage status of a suspicious activity report."""
    report = db.get(SuspiciousReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Suspicious report not found.")
    prev = report.status
    report.status = payload.status
    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="SUSPICIOUS_REPORT_UPDATED",
        entity_type="suspicious_report",
        entity_id=report.id,
        metadata={"previous_status": prev, "new_status": report.status},
    )
    db.commit()
    return {"id": report.id, "status": report.status}


@router.get("/audit-logs", response_model=list[AdminAuditLogItem])
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Retrieve recent immutable audit log events."""
    logs = db.scalars(
        select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
    ).all()
    return [
        AdminAuditLogItem(
            id=l.id,
            actor_id=l.actor_id,
            actor_role=l.actor_role,
            action=l.action,
            entity_type=l.entity_type,
            entity_id=l.entity_id,
            metadata=l.metadata_json,
            timestamp=l.timestamp,
        )
        for l in logs
    ]
