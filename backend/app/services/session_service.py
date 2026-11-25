"""Layer 5 — Communication Session Validity, Trust ID issuance, atomic redemption, and reporting."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.security import (
    generate_session_key,
    generate_trust_id,
    hash_token,
    normalize_trust_id,
    utc_now,
)
from app.db.models import (
    CommunicationSession,
    CustomerVerificationSession,
    Employee,
    SuspiciousReport,
)
from app.schemas.verification import (
    PublicAIAssessment,
    PublicCommunicationInfo,
    PublicCompanyInfo,
    PublicEmployeeInfo,
    PublicVerificationResponse,
    SuspiciousReportResponse,
)
from app.services.audit_service import record_audit_event
from app.trust_engine.ai_provider import (
    MOCK_NOTICE,
    DeepfakeAssessmentResult,
    VoiceVerificationResult,
)


def create_communication_session(
    db: Session,
    *,
    company_id: int,
    employee_id: int,
    actor_user_id: int,
    purpose: str,
    reference_note: Optional[str],
    voice_result: VoiceVerificationResult,
    deepfake_result: DeepfakeAssessmentResult,
) -> tuple[str, CommunicationSession]:
    """Generate a high-entropy single-use Trust ID and persist its hashed session."""
    settings = get_settings()
    raw_trust_id = generate_trust_id()
    trust_id_hash = hash_token(raw_trust_id)
    now = utc_now()
    expires_at = now + timedelta(minutes=settings.TRUST_ID_EXPIRY_MINUTES)

    voice_payload = {
        "success": voice_result.success,
        "decision": voice_result.decision,
        "score": voice_result.score,
        "timestamp": voice_result.timestamp.isoformat(),
        "is_mock": voice_result.is_mock,
        "notice": voice_result.notice,
        "metadata": voice_result.metadata,
    }
    deepfake_payload = {
        "success": deepfake_result.success,
        "decision": deepfake_result.decision,
        "risk_score": deepfake_result.risk_score,
        "confidence": deepfake_result.confidence,
        "timestamp": deepfake_result.timestamp.isoformat(),
        "is_mock": deepfake_result.is_mock,
        "notice": deepfake_result.notice,
        "metadata": deepfake_result.metadata,
    }

    session = CommunicationSession(
        trust_id_hash=trust_id_hash,
        company_id=company_id,
        employee_id=employee_id,
        purpose=purpose,
        reference_note=reference_note.strip() if reference_note else None,
        voice_verification_result=voice_payload,
        deepfake_assessment=deepfake_payload,
        ai_provider=voice_result.provider_name,
        is_mock=bool(voice_result.is_mock or deepfake_result.is_mock),
        status="ACTIVE",
        issued_at=now,
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()

    record_audit_event(
        db,
        actor_id=actor_user_id,
        actor_role="employee",
        action="TRUST_ID_ISSUED",
        entity_type="communication_session",
        entity_id=session.id,
        metadata={
            "company_id": company_id,
            "employee_id": employee_id,
            "purpose": purpose,
            "ai_provider": session.ai_provider,
            "is_mock": session.is_mock,
            "expires_at": expires_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(session)
    return raw_trust_id, session


def _build_public_verification_response(
    db: Session,
    comm: CommunicationSession,
    *,
    customer_session_active: bool,
) -> PublicVerificationResponse:
    """Construct a sanitized public response without internal IDs or sensitive data."""
    company = comm.company
    employee = comm.employee
    emp_user = employee.user

    report_count = db.scalar(
        select(func.count(SuspiciousReport.id)).where(
            SuspiciousReport.communication_session_id == comm.id
        )
    ) or 0
    suspicious_reported = report_count > 0

    voice_res = comm.voice_verification_result or {}
    deepfake_res = comm.deepfake_assessment or {}
    is_mock = bool(comm.is_mock)

    # Determine overall public status & clear explanation
    if suspicious_reported:
        overall_status = "Suspicious"
        status_explanation = (
            "Warning: This communication session has been flagged as suspicious by a customer. "
            "Do not share sensitive information or complete requested transactions."
        )
    elif (
        comm.revoked_at is not None
        or comm.status == "REVOKED"
        or company.verification_status != "VERIFIED"
        or not emp_user.is_active
        or employee.identity_status != "COMPANY_ATTESTED"
    ):
        overall_status = "Invalid"
        status_explanation = (
            "This communication authorization is no longer valid because the session was revoked "
            "or the issuing company/employee authorization was suspended."
        )
    elif voice_res.get("decision") != "MATCH" or deepfake_res.get("decision") != "AUTHENTIC":
        overall_status = "Suspicious"
        status_explanation = (
            "AI voice or deepfake checks indicated an anomaly on this communication session."
        )
    else:
        overall_status = "Verified"
        status_explanation = (
            "This Trust ID was issued to an authorized employee of a verified company "
            "for the stated communication purpose and passed pre-call verification checks."
        )

    session_validity = (
        "Redeemed (Single-Use Consumed)"
        if comm.redeemed_at is not None
        else comm.status
    )

    return PublicVerificationResponse(
        overall_status=overall_status,
        status_explanation=status_explanation,
        suspicious_reported=suspicious_reported,
        customer_session_active=customer_session_active,
        company=PublicCompanyInfo(
            company_name=company.company_name,
            verification_status=company.verification_status,
            industry=company.industry,
            verification_indicator=(
                "Platform-Verified Business"
                if company.verification_status == "VERIFIED"
                else f"Not Verified ({company.verification_status})"
            ),
        ),
        employee=PublicEmployeeInfo(
            full_name=emp_user.full_name,
            designation=employee.designation,
            department=employee.department,
            authorization_status=(
                "Authorized & Company-Attested"
                if emp_user.is_active and employee.identity_status == "COMPANY_ATTESTED"
                else "Inactive / Revoked"
            ),
            company_association=company.company_name,
        ),
        ai_assessment=PublicAIAssessment(
            voice_verification_decision=str(voice_res.get("decision", "UNKNOWN")),
            voice_match_score=voice_res.get("score"),
            deepfake_decision=str(deepfake_res.get("decision", "UNKNOWN")),
            deepfake_risk_score=deepfake_res.get("risk_score"),
            assessment_timestamp=comm.issued_at,
            provider_name=comm.ai_provider,
            is_mock=is_mock,
            mock_notice=MOCK_NOTICE if is_mock else None,
        ),
        communication=PublicCommunicationInfo(
            purpose=comm.purpose,
            reference_note=comm.reference_note,
            issued_at=comm.issued_at,
            expires_at=comm.expires_at,
            redeemed_at=comm.redeemed_at,
            session_validity=session_validity,
        ),
    )


def redeem_trust_id_atomically(
    db: Session,
    raw_trust_id: str,
) -> tuple[PublicVerificationResponse, Optional[str], int]:
    """
    Atomically redeem a single-use Trust ID.

    Executes the conditional UPDATE as the first database statement in the
    transaction so SQLite's write lock prevents concurrent double-redemption.
    Returns (response, raw_customer_session_key_or_none, http_status_code).
    """
    settings = get_settings()
    canonical = normalize_trust_id(raw_trust_id)
    token_hash = hash_token(canonical)
    now = utc_now()

    # Atomic conditional UPDATE first (no preceding SELECT on this session!)
    update_stmt = (
        update(CommunicationSession)
        .where(
            CommunicationSession.trust_id_hash == token_hash,
            CommunicationSession.status == "ACTIVE",
            CommunicationSession.revoked_at.is_(None),
            CommunicationSession.expires_at > now,
        )
        .values(status="REDEEMED", redeemed_at=now)
    )
    res = db.execute(update_stmt)

    if res.rowcount == 1:
        comm = db.scalar(
            select(CommunicationSession)
            .options(
                joinedload(CommunicationSession.company),
                joinedload(CommunicationSession.employee).joinedload(Employee.user),
            )
            .where(CommunicationSession.trust_id_hash == token_hash)
        )
        if not comm:
            db.rollback()
            return (
                PublicVerificationResponse(
                    overall_status="Invalid",
                    status_explanation="Trust ID could not be validated.",
                ),
                None,
                404,
            )

        # Ensure issuer and employee are still active at redemption time
        if (
            comm.company.verification_status != "VERIFIED"
            or not comm.employee.user.is_active
            or comm.employee.identity_status != "COMPANY_ATTESTED"
        ):
            comm.status = "REVOKED"
            comm.revoked_at = now
            record_audit_event(
                db,
                actor_id=None,
                actor_role="customer_anonymous",
                action="TRUST_ID_REDEEM_BLOCKED_INACTIVE_ISSUER",
                entity_type="communication_session",
                entity_id=comm.id,
            )
            db.commit()
            return (
                PublicVerificationResponse(
                    overall_status="Invalid",
                    status_explanation=(
                        "This Trust ID is invalid because the issuing company or employee "
                        "authorization is no longer active."
                    ),
                ),
                None,
                400,
            )

        raw_session_key = generate_session_key()
        session_expires = now + timedelta(minutes=settings.CUSTOMER_SESSION_EXPIRY_MINUTES)
        cust_session = CustomerVerificationSession(
            communication_session_id=comm.id,
            session_key_hash=hash_token(raw_session_key),
            created_at=now,
            expires_at=session_expires,
        )
        db.add(cust_session)
        record_audit_event(
            db,
            actor_id=None,
            actor_role="customer_anonymous",
            action="TRUST_ID_REDEEMED",
            entity_type="communication_session",
            entity_id=comm.id,
            metadata={"purpose": comm.purpose},
        )
        db.commit()
        response = _build_public_verification_response(
            db, comm, customer_session_active=True
        )
        return response, raw_session_key, 200

    # Redemption did not match ACTIVE + unexpired row; inspect reason safely.
    existing = db.scalar(
        select(CommunicationSession).where(
            CommunicationSession.trust_id_hash == token_hash
        )
    )
    if not existing:
        record_audit_event(
            db,
            actor_id=None,
            actor_role="customer_anonymous",
            action="TRUST_ID_INVALID_ATTEMPT",
            entity_type="communication_session",
            entity_id=None,
        )
        db.commit()
        return (
            PublicVerificationResponse(
                overall_status="Invalid",
                status_explanation=(
                    "No matching Trust ID was found. Verify the code with the caller "
                    "and do not trust unverified calls."
                ),
            ),
            None,
            404,
        )

    if existing.revoked_at is not None or existing.status == "REVOKED":
        record_audit_event(
            db,
            actor_id=None,
            actor_role="customer_anonymous",
            action="TRUST_ID_REVOKED_ATTEMPT",
            entity_type="communication_session",
            entity_id=existing.id,
        )
        db.commit()
        return (
            PublicVerificationResponse(
                overall_status="Invalid",
                status_explanation="This Trust ID has been revoked and is no longer valid.",
            ),
            None,
            400,
        )

    if existing.status == "REDEEMED" or existing.redeemed_at is not None:
        record_audit_event(
            db,
            actor_id=None,
            actor_role="customer_anonymous",
            action="TRUST_ID_REPLAY_ATTEMPT",
            entity_type="communication_session",
            entity_id=existing.id,
        )
        db.commit()
        return (
            PublicVerificationResponse(
                overall_status="Invalid",
                status_explanation=(
                    "This Trust ID has already been redeemed. Trust IDs are strictly "
                    "single-use and cannot be verified twice."
                ),
            ),
            None,
            409,
        )

    # Otherwise expired
    if existing.status == "ACTIVE" and existing.expires_at <= now:
        existing.status = "EXPIRED"
    record_audit_event(
        db,
        actor_id=None,
        actor_role="customer_anonymous",
        action="TRUST_ID_EXPIRED_ATTEMPT",
        entity_type="communication_session",
        entity_id=existing.id,
    )
    db.commit()
    return (
        PublicVerificationResponse(
            overall_status="Expired",
            status_explanation=(
                "This Trust ID has expired. Ask the employee to initiate a fresh "
                "pre-call verification session."
            ),
        ),
        None,
        410,
    )


def get_customer_session_verification(
    db: Session,
    raw_session_key: str,
) -> tuple[Optional[PublicVerificationResponse], str]:
    """
    Look up an active anonymous customer verification session from its HttpOnly cookie.
    Returns (response_or_none, status_code_reason).
    """
    now = utc_now()
    cust = db.scalar(
        select(CustomerVerificationSession)
        .options(
            joinedload(CustomerVerificationSession.communication_session).joinedload(
                CommunicationSession.company
            ),
            joinedload(CustomerVerificationSession.communication_session)
            .joinedload(CommunicationSession.employee)
            .joinedload(Employee.user),
        )
        .where(CustomerVerificationSession.session_key_hash == hash_token(raw_session_key))
    )
    if not cust or cust.revoked_at is not None:
        return None, "invalid"

    if cust.expires_at <= now:
        return (
            PublicVerificationResponse(
                overall_status="Expired",
                status_explanation=(
                    "Your temporary verification viewing session has expired. "
                    "Request a new Trust ID if you still need to verify the call."
                ),
                customer_session_active=False,
            ),
            "expired",
        )

    response = _build_public_verification_response(
        db, cust.communication_session, customer_session_active=True
    )
    return response, "ok"


def submit_suspicious_report(
    db: Session,
    *,
    raw_session_key: str,
    reason: str,
    description: Optional[str],
) -> SuspiciousReportResponse:
    """Persist a customer suspicious report tied to their verified customer session."""
    now = utc_now()
    cust = db.scalar(
        select(CustomerVerificationSession)
        .options(joinedload(CustomerVerificationSession.communication_session))
        .where(CustomerVerificationSession.session_key_hash == hash_token(raw_session_key))
    )
    if not cust or cust.revoked_at is not None or cust.expires_at <= now:
        raise ValueError("No active verification session found. Verify a Trust ID first.")

    comm = cust.communication_session
    report = SuspiciousReport(
        communication_session_id=comm.id,
        customer_session_id=cust.id,
        reason=reason,
        description=description.strip() if description else None,
        created_at=now,
        status="OPEN",
    )
    db.add(report)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise PermissionError("A suspicious activity report has already been submitted for this session.")

    record_audit_event(
        db,
        actor_id=None,
        actor_role="customer_anonymous",
        action="SUSPICIOUS_REPORT_SUBMITTED",
        entity_type="suspicious_report",
        entity_id=report.id,
        metadata={
            "communication_session_id": comm.id,
            "reason": reason,
        },
    )
    db.commit()
    db.refresh(report)

    return SuspiciousReportResponse(
        reported=True,
        message="Thank you. Your suspicious activity report has been recorded and escalated to platform administrators.",
        reason=report.reason,
        created_at=report.created_at,
        overall_status="Suspicious",
    )


def revoke_communication_session(
    db: Session,
    *,
    session_id: int,
    actor_id: int,
    actor_role: str,
    reason: str = "Revoked by administrator",
) -> CommunicationSession | None:
    """Revoke a communication session and any linked customer viewing sessions."""
    comm = db.get(CommunicationSession, session_id)
    if not comm:
        return None
    now = utc_now()
    comm.status = "REVOKED"
    comm.revoked_at = now
    db.execute(
        update(CustomerVerificationSession)
        .where(
            CustomerVerificationSession.communication_session_id == comm.id,
            CustomerVerificationSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    record_audit_event(
        db,
        actor_id=actor_id,
        actor_role=actor_role,
        action="COMMUNICATION_SESSION_REVOKED",
        entity_type="communication_session",
        entity_id=comm.id,
        metadata={"reason": reason},
    )
    db.commit()
    db.refresh(comm)
    return comm
