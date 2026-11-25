"""Central orchestration service combining all Five Independent Trust Layers."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import User
from app.schemas.verification import LayerResultSchema, TrustIDIssueResponse
from app.services.audit_service import record_audit_event
from app.services.business_verification import verify_business
from app.services.employee_verification import verify_employee_identity
from app.services.permission_verification import verify_communication_permission
from app.services.session_service import create_communication_session
from app.trust_engine.ai_provider import MOCK_NOTICE, ProviderConfigurationError
from app.trust_engine.factory import get_ai_provider


def run_pre_call_verification(
    db: Session,
    *,
    employee_user: User,
    purpose: str,
    reference_note: Optional[str],
    audio_data: bytes,
    mime_type: str,
    simulation_mode: Optional[str] = None,
) -> tuple[TrustIDIssueResponse, int]:
    """
    Execute all 5 trust layers sequentially.
    Refuses Trust ID generation if any mandatory check fails.
    Returns (TrustIDIssueResponse, http_status_code).
    """
    layer_results: list[LayerResultSchema] = []

    # Layer 2 first to resolve employee profile & company_id, or Layer 1 via user.company_id
    if employee_user.company_id is None:
        layer_results.append(
            LayerResultSchema(
                layer="Layer 1 — Business Verification",
                passed=False,
                status="NO_COMPANY",
                message="Authenticated user is not associated with a registered company.",
            )
        )
        record_audit_event(
            db,
            actor_id=employee_user.id,
            actor_role=employee_user.role,
            action="PRECALL_VERIFICATION_FAILED",
            entity_type="user",
            entity_id=employee_user.id,
            metadata={"failed_layer": "Layer 1", "reason": "NO_COMPANY"},
        )
        db.commit()
        return (
            TrustIDIssueResponse(
                issued=False,
                overall_status="FAILED",
                purpose=purpose,
                reference_note=reference_note,
                ai_provider="none",
                is_mock=False,
                layer_results=layer_results,
            ),
            403,
        )

    # Layer 1 — Business Verification
    biz = verify_business(db, employee_user.company_id)
    layer_results.append(
        LayerResultSchema(
            layer="Layer 1 — Business Verification",
            passed=biz.passed,
            status=biz.status,
            message=biz.message,
            details=biz.details,
        )
    )
    if not biz.passed:
        record_audit_event(
            db,
            actor_id=employee_user.id,
            actor_role=employee_user.role,
            action="PRECALL_VERIFICATION_FAILED",
            entity_type="company",
            entity_id=employee_user.company_id,
            metadata={"failed_layer": "Layer 1", "status": biz.status},
        )
        db.commit()
        return (
            TrustIDIssueResponse(
                issued=False,
                overall_status="FAILED",
                purpose=purpose,
                reference_note=reference_note,
                ai_provider="none",
                is_mock=False,
                layer_results=layer_results,
            ),
            403,
        )

    # Layer 2 — Employee Identity Verification
    emp_res = verify_employee_identity(db, employee_user)
    layer_results.append(
        LayerResultSchema(
            layer="Layer 2 — Employee Identity Verification",
            passed=emp_res.passed,
            status=emp_res.status,
            message=emp_res.message,
            details=emp_res.details,
        )
    )
    if not emp_res.passed or emp_res.employee is None:
        record_audit_event(
            db,
            actor_id=employee_user.id,
            actor_role=employee_user.role,
            action="PRECALL_VERIFICATION_FAILED",
            entity_type="employee",
            entity_id=emp_res.employee.id if emp_res.employee else None,
            metadata={"failed_layer": "Layer 2", "status": emp_res.status},
        )
        db.commit()
        return (
            TrustIDIssueResponse(
                issued=False,
                overall_status="FAILED",
                purpose=purpose,
                reference_note=reference_note,
                ai_provider="none",
                is_mock=False,
                layer_results=layer_results,
            ),
            403,
        )

    employee = emp_res.employee

    # Layer 4 — Authority and Permission Verification (checked before or alongside AI)
    perm_res = verify_communication_permission(employee, purpose)
    layer_results.append(
        LayerResultSchema(
            layer="Layer 4 — Authority & Permission Verification",
            passed=perm_res.passed,
            status=perm_res.status,
            message=perm_res.message,
            details=perm_res.details,
        )
    )
    if not perm_res.passed:
        record_audit_event(
            db,
            actor_id=employee_user.id,
            actor_role=employee_user.role,
            action="PRECALL_VERIFICATION_FAILED",
            entity_type="employee",
            entity_id=employee.id,
            metadata={
                "failed_layer": "Layer 4",
                "status": perm_res.status,
                "purpose": purpose,
            },
        )
        db.commit()
        return (
            TrustIDIssueResponse(
                issued=False,
                overall_status="FAILED",
                purpose=purpose,
                reference_note=reference_note,
                ai_provider="none",
                is_mock=False,
                layer_results=layer_results,
            ),
            403,
        )

    # Layer 3 — AI Voice and Deepfake Verification
    try:
        provider = get_ai_provider()
    except ProviderConfigurationError as exc:
        layer_results.append(
            LayerResultSchema(
                layer="Layer 3 — AI Voice & Deepfake Verification",
                passed=False,
                status="PROVIDER_UNCONFIGURED",
                message=str(exc),
            )
        )
        return (
            TrustIDIssueResponse(
                issued=False,
                overall_status="PROVIDER_ERROR",
                purpose=purpose,
                reference_note=reference_note,
                ai_provider="unconfigured",
                is_mock=False,
                layer_results=layer_results,
            ),
            503,
        )

    # Only honor simulation_mode when mock provider is active
    effective_sim = simulation_mode if provider.is_mock else None
    voice_res = provider.verify_voice(
        employee.id,
        audio_data,
        mime_type=mime_type,
        simulation_mode=effective_sim,
    )
    deepfake_res = provider.detect_deepfake(
        audio_data,
        employee_id=employee.id,
        mime_type=mime_type,
        simulation_mode=effective_sim,
    )

    ai_passed = bool(voice_res.success and deepfake_res.success)
    err_notes = [
        m
        for m in (
            voice_res.metadata.get("error_message") or voice_res.metadata.get("error"),
            deepfake_res.metadata.get("error_message") or deepfake_res.metadata.get("error"),
        )
        if m
    ]
    fail_msg = (
        " ".join(dict.fromkeys(str(x) for x in err_notes))
        if err_notes
        else "AI voice or deepfake verification check failed. Trust ID denied."
    )
    layer_results.append(
        LayerResultSchema(
            layer="Layer 3 — AI Voice & Deepfake Verification",
            passed=ai_passed,
            status=(
                "VERIFIED"
                if ai_passed
                else f"{voice_res.decision} / {deepfake_res.decision}"
            ),
            message=(
                "Voice match and deepfake assessment passed."
                if ai_passed
                else fail_msg
            ),
            details={
                "provider": provider.provider_name,
                "is_mock": provider.is_mock,
                "mock_notice": MOCK_NOTICE if provider.is_mock else None,
                "voice_decision": voice_res.decision,
                "voice_score": voice_res.score,
                "deepfake_decision": deepfake_res.decision,
                "deepfake_risk_score": deepfake_res.risk_score,
            },
        )
    )

    if not ai_passed:
        record_audit_event(
            db,
            actor_id=employee_user.id,
            actor_role=employee_user.role,
            action="PRECALL_AI_CHECK_FAILED",
            entity_type="employee",
            entity_id=employee.id,
            metadata={
                "failed_layer": "Layer 3",
                "voice_decision": voice_res.decision,
                "voice_score": voice_res.score,
                "deepfake_decision": deepfake_res.decision,
                "deepfake_risk_score": deepfake_res.risk_score,
                "ai_provider": provider.provider_name,
                "is_mock": provider.is_mock,
            },
        )
        db.commit()
        return (
            TrustIDIssueResponse(
                issued=False,
                overall_status="FAILED",
                purpose=purpose,
                reference_note=reference_note,
                ai_provider=provider.provider_name,
                is_mock=provider.is_mock,
                mock_notice=MOCK_NOTICE if provider.is_mock else None,
                layer_results=layer_results,
            ),
            403,
        )

    # Layer 5 — Communication Session Validity (Issue Trust ID)
    raw_trust_id, comm_session = create_communication_session(
        db,
        company_id=employee.company_id,
        employee_id=employee.id,
        actor_user_id=employee_user.id,
        purpose=purpose,
        reference_note=reference_note,
        voice_result=voice_res,
        deepfake_result=deepfake_res,
    )

    layer_results.append(
        LayerResultSchema(
            layer="Layer 5 — Communication Session Validity",
            passed=True,
            status="ISSUED",
            message="Single-use Trust ID issued and stored securely as a cryptographic hash.",
            details={
                "issued_at": comm_session.issued_at.isoformat(),
                "expires_at": comm_session.expires_at.isoformat(),
                "single_use": True,
            },
        )
    )

    return (
        TrustIDIssueResponse(
            trust_id=raw_trust_id,
            issued=True,
            overall_status="VERIFIED",
            purpose=comm_session.purpose,
            reference_note=comm_session.reference_note,
            issued_at=comm_session.issued_at,
            expires_at=comm_session.expires_at,
            ai_provider=comm_session.ai_provider,
            is_mock=comm_session.is_mock,
            mock_notice=MOCK_NOTICE if comm_session.is_mock else None,
            layer_results=layer_results,
        ),
        201,
    )
