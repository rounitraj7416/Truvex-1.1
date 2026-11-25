"""Voice enrollment and pre-call verification routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.dependencies import require_roles
from app.core.security import utc_now
from app.db.database import get_db
from app.db.models import Employee, User, VoiceEnrollment
from app.schemas.verification import TrustIDIssueResponse, VoiceEnrollmentResponse
from app.services.audit_service import record_audit_event
from app.services.verification_orchestrator import run_pre_call_verification
from app.trust_engine.ai_provider import MOCK_NOTICE, ProviderConfigurationError
from app.trust_engine.factory import get_ai_provider

router = APIRouter(prefix="/api/verification", tags=["Verification"])

ALLOWED_AUDIO_MIME_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    "audio/aac",
    "audio/mpeg",
    "audio/mp3",
    "audio/flac",
    "audio/x-flac",
    "video/webm",
}

_EXT_TO_AUDIO_MIME = {
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".mp4": "audio/mp4",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
}


async def _read_and_validate_audio(audio: UploadFile) -> tuple[bytes, str]:
    """Validate uploaded audio MIME type and size, keeping payload in memory only."""
    settings = get_settings()
    raw_content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
    if raw_content_type in ("", "application/octet-stream") and audio.filename:
        suffix = "." + audio.filename.rsplit(".", 1)[-1].lower() if "." in audio.filename else ""
        raw_content_type = _EXT_TO_AUDIO_MIME.get(suffix, raw_content_type)
    if raw_content_type not in ALLOWED_AUDIO_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported audio media type '{raw_content_type or 'unknown'}'. "
                "Please record audio in WebM, OGG, WAV, MP4, or MP3 format."
            ),
        )

    max_bytes = settings.MAX_AUDIO_UPLOAD_BYTES
    data = await audio.read(max_bytes + 1)
    await audio.close()

    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Audio upload exceeds maximum allowed size of {max_bytes // (1024 * 1024)} MB.",
        )

    if len(data) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recorded audio sample is too short or empty. Please record a clear sample.",
        )

    return data, raw_content_type


@router.post("/voice-enroll", response_model=VoiceEnrollmentResponse)
async def enroll_employee_voice(
    consent: bool = Form(...),
    simulation_mode: Optional[str] = Form(default=None),
    audio: UploadFile = File(...),
    current_user: User = Depends(require_roles("employee")),
    db: Session = Depends(get_db),
):
    """Enroll an authenticated employee's voice after explicit consent."""
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit employee consent is required prior to voice enrollment.",
        )

    employee = db.scalar(
        select(Employee)
        .options(joinedload(Employee.company))
        .where(Employee.user_id == current_user.id)
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not found.")

    if employee.company.verification_status != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your company must be VERIFIED before voice enrollment is permitted.",
        )

    audio_bytes, mime_type = await _read_and_validate_audio(audio)

    try:
        provider = get_ai_provider()
    except ProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    effective_sim = simulation_mode if provider.is_mock else None
    result = provider.enroll_voice(
        employee.id,
        audio_bytes,
        mime_type=mime_type,
        simulation_mode=effective_sim,
    )

    now = utc_now()
    enrollment = VoiceEnrollment(
        employee_id=employee.id,
        provider=result.provider_name,
        is_mock=result.is_mock,
        status="ENROLLED" if result.success else "FAILED",
        consent_given=True,
        consent_timestamp=now,
        enrolled_at=result.timestamp,
        metadata_json={
            "decision": result.decision,
            "score": result.score,
            "notice": result.notice,
            **result.metadata,
        },
    )
    db.add(enrollment)

    if result.success:
        employee.voice_enrolled = True

    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="VOICE_ENROLLED" if result.success else "VOICE_ENROLLMENT_FAILED",
        entity_type="employee",
        entity_id=employee.id,
        metadata={
            "provider": result.provider_name,
            "is_mock": result.is_mock,
            "decision": result.decision,
            "score": result.score,
        },
    )
    db.commit()

    if not result.success:
        reason = (
            result.metadata.get("error_message")
            or result.metadata.get("error")
            or "Voice enrollment did not succeed. Please try recording or uploading a clearer audio sample."
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=reason,
        )

    return VoiceEnrollmentResponse(
        enrolled=True,
        status="ENROLLED",
        provider=result.provider_name,
        is_mock=result.is_mock,
        mock_notice=MOCK_NOTICE if result.is_mock else None,
        enrolled_at=result.timestamp,
        metadata=enrollment.metadata_json or {},
    )


@router.post("/pre-call", response_model=TrustIDIssueResponse)
async def initiate_pre_call_verification(
    purpose: str = Form(...),
    reference_note: Optional[str] = Form(default=None),
    simulation_mode: Optional[str] = Form(default=None),
    audio: UploadFile = File(...),
    current_user: User = Depends(require_roles("employee")),
    db: Session = Depends(get_db),
):
    """Run all 5 independent trust layers and issue a single-use Trust ID on full pass."""
    audio_bytes, mime_type = await _read_and_validate_audio(audio)

    response_payload, status_code = run_pre_call_verification(
        db,
        employee_user=current_user,
        purpose=purpose,
        reference_note=reference_note,
        audio_data=audio_bytes,
        mime_type=mime_type,
        simulation_mode=simulation_mode,
    )
    return JSONResponse(
        status_code=status_code,
        content=response_payload.model_dump(mode="json"),
    )
