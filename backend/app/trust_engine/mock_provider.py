"""Deterministic mock AI provider for offline MVP execution and demonstrations."""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from app.core.config import get_settings
from app.core.security import utc_now
from app.trust_engine.ai_provider import (
    MOCK_NOTICE,
    AIProvider,
    DeepfakeAssessmentResult,
    VoiceEnrollmentResult,
    VoiceVerificationResult,
)

logger = logging.getLogger(__name__)


class MockAIProvider(AIProvider):
    """
    Deterministic mock AI provider.

    HONESTY REQUIREMENT:
    This provider does NOT perform real acoustic analysis, speaker recognition,
    or deepfake detection. It produces deterministic simulated scores per
    employee and supports explicit test/demo failure scenarios.
    """

    provider_name = "mock-aletheia-eidos-simulator"
    is_mock = True

    def _deterministic_unit(self, seed_key: str) -> float:
        digest = hashlib.sha256(seed_key.encode("utf-8")).digest()
        val = int.from_bytes(digest[:4], "big")
        return val / 0xFFFFFFFF

    def enroll_voice(
        self,
        employee_id: int,
        audio_data: bytes,
        *,
        mime_type: str = "audio/webm",
        simulation_mode: Optional[str] = None,
    ) -> VoiceEnrollmentResult:
        now = utc_now()
        if not audio_data or len(audio_data) < 100:
            logger.info("Mock enrollment rejected empty/short audio for employee_id=%s", employee_id)
            return VoiceEnrollmentResult(
                success=False,
                decision="REJECTED_AUDIO_TOO_SHORT",
                provider_name=self.provider_name,
                is_mock=True,
                timestamp=now,
                score=0.0,
                notice=MOCK_NOTICE,
                metadata={
                    "simulated": True,
                    "audio_bytes": len(audio_data) if audio_data else 0,
                    "mime_type": mime_type,
                    "reason": "Audio payload too small for simulated enrollment.",
                },
            )

        if simulation_mode == "enroll_fail":
            logger.info("Mock enrollment simulated failure for employee_id=%s", employee_id)
            return VoiceEnrollmentResult(
                success=False,
                decision="ENROLLMENT_FAILED",
                provider_name=self.provider_name,
                is_mock=True,
                timestamp=now,
                score=0.31,
                notice=MOCK_NOTICE,
                metadata={
                    "simulated": True,
                    "simulation_mode": "enroll_fail",
                    "audio_bytes": len(audio_data),
                    "mime_type": mime_type,
                },
            )

        unit = self._deterministic_unit(f"enroll:{employee_id}")
        quality_score = round(0.84 + unit * 0.14, 4)  # 0.8400 .. 0.9800

        logger.info(
            "DEMO MODE mock voice enrollment completed for employee_id=%s score=%s",
            employee_id,
            quality_score,
        )
        return VoiceEnrollmentResult(
            success=True,
            decision="ENROLLED",
            provider_name=self.provider_name,
            is_mock=True,
            timestamp=now,
            score=quality_score,
            notice=MOCK_NOTICE,
            metadata={
                "simulated": True,
                "profile_ref": f"mock-voiceprint-emp-{employee_id}",
                "audio_bytes": len(audio_data),
                "mime_type": mime_type,
                "quality_score": quality_score,
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
        settings = get_settings()
        now = utc_now()
        threshold = settings.MOCK_VOICE_PASS_THRESHOLD

        if not audio_data or len(audio_data) < 100:
            return VoiceVerificationResult(
                success=False,
                decision="ERROR",
                provider_name=self.provider_name,
                is_mock=True,
                timestamp=now,
                score=0.0,
                notice=MOCK_NOTICE,
                metadata={"simulated": True, "reason": "Audio payload too small."},
            )

        if simulation_mode == "voice_mismatch":
            unit = self._deterministic_unit(f"mismatch:{employee_id}")
            score = round(0.22 + unit * 0.25, 4)  # 0.22 .. 0.47
            logger.info(
                "DEMO MODE simulated voice mismatch for employee_id=%s score=%s",
                employee_id,
                score,
            )
            return VoiceVerificationResult(
                success=False,
                decision="NO_MATCH",
                provider_name=self.provider_name,
                is_mock=True,
                timestamp=now,
                score=score,
                notice=MOCK_NOTICE,
                metadata={
                    "simulated": True,
                    "simulation_mode": "voice_mismatch",
                    "threshold": threshold,
                    "audio_bytes": len(audio_data),
                    "mime_type": mime_type,
                },
            )

        unit = self._deterministic_unit(f"verify:{employee_id}")
        score = round(0.83 + unit * 0.14, 4)  # 0.83 .. 0.97
        passed = score >= threshold
        logger.info(
            "DEMO MODE mock voice verification employee_id=%s score=%s passed=%s",
            employee_id,
            score,
            passed,
        )
        return VoiceVerificationResult(
            success=passed,
            decision="MATCH" if passed else "NO_MATCH",
            provider_name=self.provider_name,
            is_mock=True,
            timestamp=now,
            score=score,
            notice=MOCK_NOTICE,
            metadata={
                "simulated": True,
                "simulation_mode": simulation_mode or "normal",
                "threshold": threshold,
                "audio_bytes": len(audio_data),
                "mime_type": mime_type,
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
        settings = get_settings()
        now = utc_now()
        max_risk = settings.MOCK_DEEPFAKE_MAX_RISK

        if not audio_data or len(audio_data) < 100:
            return DeepfakeAssessmentResult(
                success=False,
                decision="ERROR",
                provider_name=self.provider_name,
                is_mock=True,
                timestamp=now,
                risk_score=1.0,
                confidence=0.0,
                notice=MOCK_NOTICE,
                metadata={"simulated": True, "reason": "Audio payload too small."},
            )

        if simulation_mode == "deepfake_detected":
            unit = self._deterministic_unit(f"deepfake:{employee_id or 0}")
            risk_score = round(0.78 + unit * 0.19, 4)  # 0.78 .. 0.97
            confidence = round(0.85 + unit * 0.12, 4)
            logger.info(
                "DEMO MODE simulated deepfake detection employee_id=%s risk=%s",
                employee_id,
                risk_score,
            )
            return DeepfakeAssessmentResult(
                success=False,
                decision="DEEPFAKE_SUSPECTED",
                provider_name=self.provider_name,
                is_mock=True,
                timestamp=now,
                risk_score=risk_score,
                confidence=confidence,
                notice=MOCK_NOTICE,
                metadata={
                    "simulated": True,
                    "simulation_mode": "deepfake_detected",
                    "max_allowed_risk": max_risk,
                    "audio_bytes": len(audio_data),
                    "mime_type": mime_type,
                },
            )

        unit = self._deterministic_unit(f"authentic:{employee_id or 0}")
        risk_score = round(0.04 + unit * 0.14, 4)  # 0.04 .. 0.18
        confidence = round(0.86 + unit * 0.11, 4)
        passed = risk_score <= max_risk
        logger.info(
            "DEMO MODE mock deepfake assessment employee_id=%s risk=%s passed=%s",
            employee_id,
            risk_score,
            passed,
        )
        return DeepfakeAssessmentResult(
            success=passed,
            decision="AUTHENTIC" if passed else "DEEPFAKE_SUSPECTED",
            provider_name=self.provider_name,
            is_mock=True,
            timestamp=now,
            risk_score=risk_score,
            confidence=confidence,
            notice=MOCK_NOTICE,
            metadata={
                "simulated": True,
                "simulation_mode": simulation_mode or "normal",
                "max_allowed_risk": max_risk,
                "audio_bytes": len(audio_data),
                "mime_type": mime_type,
            },
        )
