"""Employee management (company_admin) and employee self-service routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import require_roles
from app.core.security import hash_password
from app.db.database import get_db
from app.db.models import (
    CommunicationSession,
    Company,
    Employee,
    SuspiciousReport,
    User,
    VoiceEnrollment,
)
from app.schemas.employee import (
    ALLOWED_COMMUNICATION_PURPOSES,
    EmployeeCreateRequest,
    EmployeeResponse,
    EmployeeUpdateRequest,
)
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api/employees", tags=["Employees"])


def _serialize_employee(db: Session, emp: Employee) -> EmployeeResponse:
    latest_enrollment = db.scalar(
        select(VoiceEnrollment)
        .where(VoiceEnrollment.employee_id == emp.id)
        .order_by(VoiceEnrollment.enrolled_at.desc())
        .limit(1)
    )
    enrollment_dict = None
    if latest_enrollment:
        enrollment_dict = {
            "provider": latest_enrollment.provider,
            "is_mock": latest_enrollment.is_mock,
            "status": latest_enrollment.status,
            "consent_given": latest_enrollment.consent_given,
            "enrolled_at": latest_enrollment.enrolled_at,
            "metadata": latest_enrollment.metadata_json,
        }
    return EmployeeResponse(
        id=emp.id,
        user_id=emp.user_id,
        company_id=emp.company_id,
        company_name=emp.company.company_name,
        company_status=emp.company.verification_status,
        full_name=emp.user.full_name,
        email=emp.user.email,
        employee_code=emp.employee_code,
        designation=emp.designation,
        department=emp.department,
        assigned_role=emp.assigned_role,
        identity_status=emp.identity_status,
        allowed_purposes=list(emp.allowed_purposes or []),
        voice_enrolled=emp.voice_enrolled,
        is_active=emp.user.is_active,
        latest_enrollment=enrollment_dict,
        created_at=emp.created_at,
    )


@router.get("/purposes")
def list_supported_purposes():
    """Return the platform's supported communication purpose catalog."""
    return {"purposes": ALLOWED_COMMUNICATION_PURPOSES}


@router.get("/me", response_model=EmployeeResponse)
def get_my_employee_profile(
    current_user: User = Depends(require_roles("employee")),
    db: Session = Depends(get_db),
):
    """Return the authenticated employee's own profile and voice enrollment status."""
    emp = db.scalar(
        select(Employee)
        .options(joinedload(Employee.user), joinedload(Employee.company))
        .where(Employee.user_id == current_user.id)
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found.")
    return _serialize_employee(db, emp)


@router.get("/me/sessions")
def get_my_sessions(
    current_user: User = Depends(require_roles("employee")),
    db: Session = Depends(get_db),
):
    """Return recent communication sessions initiated by the authenticated employee."""
    emp = db.scalar(select(Employee).where(Employee.user_id == current_user.id))
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found.")

    sessions = db.scalars(
        select(CommunicationSession)
        .where(CommunicationSession.employee_id == emp.id)
        .order_by(CommunicationSession.issued_at.desc())
        .limit(30)
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
                "purpose": s.purpose,
                "reference_note": s.reference_note,
                "status": s.status,
                "ai_provider": s.ai_provider,
                "is_mock": s.is_mock,
                "issued_at": s.issued_at,
                "expires_at": s.expires_at,
                "redeemed_at": s.redeemed_at,
                "suspicious_report_count": report_count,
            }
        )
    return {"sessions": items}


@router.get("", response_model=list[EmployeeResponse])
def list_company_employees(
    current_user: User = Depends(require_roles("company_admin")),
    db: Session = Depends(get_db),
):
    """List employees belonging strictly to the company_admin's company."""
    employees = db.scalars(
        select(Employee)
        .options(joinedload(Employee.user), joinedload(Employee.company))
        .where(Employee.company_id == current_user.company_id)
        .order_by(Employee.created_at.desc())
    ).all()
    return [_serialize_employee(db, emp) for emp in employees]


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreateRequest,
    current_user: User = Depends(require_roles("company_admin")),
    db: Session = Depends(get_db),
):
    """Create an authenticated employee account for a VERIFIED company."""
    company = db.get(Company, current_user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    if company.verification_status != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Company status is {company.verification_status}. "
                "Only VERIFIED companies can register authorized employees."
            ),
        )

    email_norm = payload.email.strip().lower()
    if db.scalar(select(User).where(User.email == email_norm)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    code_norm = payload.employee_code.strip().upper()
    existing_code = db.scalar(
        select(Employee).where(
            Employee.company_id == company.id,
            Employee.employee_code == code_norm,
        )
    )
    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This employee ID code is already registered in your company.",
        )

    emp_user = User(
        email=email_norm,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role="employee",
        company_id=company.id,
        is_active=True,
    )
    db.add(emp_user)
    db.flush()

    employee = Employee(
        user_id=emp_user.id,
        company_id=company.id,
        employee_code=code_norm,
        designation=payload.designation.strip(),
        department=payload.department.strip(),
        assigned_role=payload.assigned_role.strip(),
        identity_status="COMPANY_ATTESTED",
        allowed_purposes=payload.allowed_purposes,
        voice_enrolled=False,
    )
    db.add(employee)
    db.flush()

    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="EMPLOYEE_CREATED",
        entity_type="employee",
        entity_id=employee.id,
        metadata={
            "company_id": company.id,
            "employee_code": employee.employee_code,
            "allowed_purposes": employee.allowed_purposes,
        },
    )
    db.commit()

    loaded = db.scalar(
        select(Employee)
        .options(joinedload(Employee.user), joinedload(Employee.company))
        .where(Employee.id == employee.id)
    )
    assert loaded is not None
    return _serialize_employee(db, loaded)


@router.patch("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    current_user: User = Depends(require_roles("company_admin")),
    db: Session = Depends(get_db),
):
    """Update employee permissions or activation status within the company_admin's company."""
    employee = db.scalar(
        select(Employee)
        .options(joinedload(Employee.user), joinedload(Employee.company))
        .where(Employee.id == employee_id)
    )
    if not employee or employee.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Employee not found.")

    changes = {}
    if payload.designation is not None:
        employee.designation = payload.designation.strip()
        changes["designation"] = employee.designation
    if payload.department is not None:
        employee.department = payload.department.strip()
        changes["department"] = employee.department
    if payload.assigned_role is not None:
        employee.assigned_role = payload.assigned_role.strip()
        changes["assigned_role"] = employee.assigned_role
    if payload.allowed_purposes is not None:
        employee.allowed_purposes = payload.allowed_purposes
        changes["allowed_purposes"] = employee.allowed_purposes
    if payload.is_active is not None:
        employee.user.is_active = payload.is_active
        employee.identity_status = "COMPANY_ATTESTED" if payload.is_active else "REVOKED"
        changes["is_active"] = payload.is_active

    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="EMPLOYEE_UPDATED",
        entity_type="employee",
        entity_id=employee.id,
        metadata={"changes": changes},
    )
    db.commit()
    db.refresh(employee)
    return _serialize_employee(db, employee)
