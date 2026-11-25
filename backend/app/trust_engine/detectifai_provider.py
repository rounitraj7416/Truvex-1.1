"""DetectifAI Aletheia (deepfake) + Eidos (speaker verification) provider adapter."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

import httpx

from app.core.config import get_settings
from app.core.security import utc_now
from app.trust_engine.ai_provider import (
    AIProvider,
    DeepfakeAssessmentResult,
    ProviderConfigurationError,
    VoiceEnrollmentResult,
    VoiceVerificationResult,
)

logger = logging.getLogger(__name__)

_MIME_TO_EXT = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/aac": "aac",
    "audio/flac": "flac",
}


class DetectifAIProvider(AIProvider):
    """
    Adapter for DetectifAI Platform API (https://platform.detectif.ai):
      - Eidos Speaker Enrollment:   POST /v1/speakers/enroll
      - Eidos Speaker Verification: POST /v1/speakers/verify
      - Aletheia Deepfake Detect:   POST /v1/deepfake/detect
    """

    provider_name = "detectifai-aletheia-eidos"
    is_mock = False

    def __init__(self, timeout_seconds: float = 45.0) -> None:
        self._timeout = timeout_seconds

    def _ensure_configured(self) -> tuple[str, str]:
        settings = get_settings()
        base_url = settings.DETECTIFAI_API_BASE_URL.strip().rstrip("/")
        api_key = settings.DETECTIFAI_API_KEY.strip()

        missing = []
        if not base_url:
            missing.append("DETECTIFAI_API_BASE_URL")
        if not api_key:
            missing.append("DETECTIFAI_API_KEY")

        if missing:
            raise ProviderConfigurationError(
                "DetectifAI provider is not configured. Missing environment variables: "
                + ", ".join(missing)
                + ". Use AI_PROVIDER=mock for demo mode."
            )
        return base_url, api_key

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Idempotency-Key": str(uuid.uuid4()),
        }

    def _filename(self, prefix: str, mime_type: str) -> str:
        base_mime = (mime_type or "audio/webm").split(";", 1)[0].strip().lower()
        ext = _MIME_TO_EXT.get(base_mime, "webm")
        return f"{prefix}.{ext}"

    def _speaker_id(self, employee_id: int) -> str:
        return f"emp-{employee_id}"

    def _extract_error(self, response: httpx.Response) -> tuple[str, str]:
        try:
            body = response.json()
            err = body.get("error") if isinstance(body, dict) else None
            if isinstance(err, dict):
                return str(err.get("code", f"http_{response.status_code}")), str(
                    err.get("message", response.text[:200])
                )
            if isinstance(body, dict) and "detail" in body:
                return f"http_{response.status_code}", str(body["detail"])
        except ValueError:
            pass
        return f"http_{response.status_code}", f"DetectifAI returned HTTP {response.status_code}."

    def enroll_voice(
        self,
        employee_id: int,
        audio_data: bytes,
        *,
        mime_type: str = "audio/webm",
        simulation_mode: Optional[str] = None,
    ) -> VoiceEnrollmentResult:
        base_url, api_key = self._ensure_configured()
        now = utc_now()
        speaker_id = self._speaker_id(employee_id)
        filename = self._filename(f"enroll_{speaker_id}", mime_type)

        try:
            with httpx.Client(base_url=base_url, timeout=self._timeout) as client:
                resp = client.post(
                    "/v1/speakers/enroll",
                    headers=self._headers(api_key),
                    data={"speaker_id": speaker_id},
                    files={"file": (filename, audio_data, mime_type)},
                )
        except httpx.HTTPError as exc:
            logger.warning("DetectifAI enroll request failed for employee_id=%s: %s", employee_id, type(exc).__name__)
            return VoiceEnrollmentResult(
                success=False,
                decision="ERROR",
                provider_name=self.provider_name,
                is_mock=False,
                timestamp=now,
                metadata={"error": "Failed to reach DetectifAI enrollment API."},
            )

        if resp.status_code >= 400:
            code, msg = self._extract_error(resp)
            logger.warning(
                "DetectifAI enroll HTTP %s for employee_id=%s code=%s",
                resp.status_code,
                employee_id,
                code,
            )
            return VoiceEnrollmentResult(
                success=False,
                decision="ENROLLMENT_FAILED",
                provider_name=self.provider_name,
                is_mock=False,
                timestamp=now,
                metadata={"error_code": code, "error_message": msg},
            )

        payload = resp.json()
        status_val = str(payload.get("status", "enrolled")).lower()
        ok = status_val == "enrolled"
        return VoiceEnrollmentResult(
            success=ok,
            decision="ENROLLED" if ok else status_val.upper(),
            provider_name=self.provider_name,
            is_mock=False,
            timestamp=now,
            metadata={
                "request_id": payload.get("request_id"),
                "speaker_id": payload.get("speaker_id", speaker_id),
                "samples_count": payload.get("samples_count"),
                "duration_seconds": payload.get("duration_seconds"),
            },
        )

    def verify_voice(
        self,
        employee_id: int,
        audio_data: bytes,
        *,
        mime_type: str = "audio/webm",
        simulation_mode: Optional[str] = None,
    ) -> VoiceVerificationResult:
        base_url, api_key = self._ensure_configured()
        now = utc_now()
        speaker_id = self._speaker_id(employee_id)
        filename = self._filename(f"verify_{speaker_id}", mime_type)

        try:
            with httpx.Client(base_url=base_url, timeout=self._timeout) as client:
                resp = client.post(
                    "/v1/speakers/verify",
                    headers=self._headers(api_key),
                    data={"speaker_id": speaker_id},
                    files={"file": (filename, audio_data, mime_type)},
                )
        except httpx.HTTPError as exc:
            logger.warning("DetectifAI verify request failed for employee_id=%s: %s", employee_id, type(exc).__name__)
            return VoiceVerificationResult(
                success=False,
                decision="ERROR",
                provider_name=self.provider_name,
                is_mock=False,
                timestamp=now,
                metadata={"error": "Failed to reach DetectifAI speaker verification API."},
            )

        if resp.status_code >= 400:
            code, msg = self._extract_error(resp)
            logger.warning(
                "DetectifAI verify HTTP %s for employee_id=%s code=%s",
                resp.status_code,
                employee_id,
                code,
            )
            return VoiceVerificationResult(
                success=False,
                decision="ERROR",
                provider_name=self.provider_name,
                is_mock=False,
                timestamp=now,
                metadata={
                    "error_code": code,
                    "error_message": (
                        "Speaker voiceprint not found on DetectifAI. Complete Step 1 Voice Enrollment first."
                        if resp.status_code == 404
                        else msg
                    ),
                },
            )

        payload = resp.json()
        result = payload.get("result") or {}
        decision_raw = str(result.get("decision") or result.get("verdict") or "").lower()
        similarity = result.get("similarity")
        if similarity is None:
            similarity = result.get("score")
        score_val = float(similarity) if similarity is not None else None
        matched = decision_raw == "match"

        return VoiceVerificationResult(
            success=matched,
            decision="MATCH" if matched else "NO_MATCH",
            provider_name=self.provider_name,
            is_mock=False,
            timestamp=now,
            score=score_val,
            metadata={
                "request_id": payload.get("request_id"),
                "speaker_id": payload.get("speaker_id", speaker_id),
                "raw_decision": decision_raw,
                "duration_seconds": result.get("duration_seconds"),
            },
        )

    def detect_deepfake(
        self,
        audio_data: bytes,
        *,
        employee_id: Optional[int] = None,
        mime_type: str = "audio/webm",
        simulation_mode: Optional[str] = None,
    ) -> DeepfakeAssessmentResult:
        base_url, api_key = self._ensure_configured()
        now = utc_now()
        filename = self._filename(f"deepfake_{employee_id or 'call'}", mime_type)

        try:
            with httpx.Client(base_url=base_url, timeout=self._timeout) as client:
                resp = client.post(
                    "/v1/deepfake/detect",
                    headers=self._headers(api_key),
                    files={"file": (filename, audio_data, mime_type)},
                )
        except httpx.HTTPError as exc:
            logger.warning("DetectifAI deepfake request failed: %s", type(exc).__name__)
            return DeepfakeAssessmentResult(
                success=False,
                decision="ERROR",
                provider_name=self.provider_name,
                is_mock=False,
                timestamp=now,
                metadata={"error": "Failed to reach DetectifAI deepfake detection API."},
            )

        if resp.status_code >= 400:
            code, msg = self._extract_error(resp)
            logger.warning("DetectifAI deepfake HTTP %s code=%s", resp.status_code, code)
            return DeepfakeAssessmentResult(
                success=False,
                decision="ERROR",
                provider_name=self.provider_name,
                is_mock=False,
                timestamp=now,
                metadata={"error_code": code, "error_message": msg},
            )

        payload = resp.json()
        result = payload.get("result") or {}
        verdict = str(result.get("verdict") or result.get("decision") or "").lower()
        score_raw = result.get("score")
        risk_score = float(score_raw) if score_raw is not None else None
        authentic = verdict in {"real", "pass", "authentic", "human"}

        return DeepfakeAssessmentResult(
            success=authentic,
            decision="AUTHENTIC" if authentic else "DEEPFAKE_SUSPECTED",
            provider_name=self.provider_name,
            is_mock=False,
            timestamp=now,
            risk_score=risk_score,
            confidence=(round(1.0 - risk_score, 4) if authentic and risk_score is not None else risk_score),
            metadata={
                "request_id": payload.get("request_id"),
                "operation_id": payload.get("operation_id"),
                "raw_verdict": verdict,
                "duration_seconds": result.get("duration_seconds"),
                "scored_seconds": result.get("scored_seconds"),
                "segments_count": len(result.get("segments") or []),
            },
        )
