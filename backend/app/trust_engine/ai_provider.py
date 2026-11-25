"""Abstract AI provider interface and structured results for Layer 3 (Voice & Deepfake)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

MOCK_NOTICE = (
    "DEMO MODE — AI assessment simulated using a mock provider. "
    "No real deepfake detection was performed."
)


class ProviderConfigurationError(RuntimeError):
    """Raised when a configured external AI provider lacks credentials or API specs."""


@dataclass(slots=True)
class VoiceEnrollmentResult:
    success: bool
    decision: str
    provider_name: str
    is_mock: bool
    timestamp: datetime
    score: Optional[float] = None
    notice: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VoiceVerificationResult:
    success: bool
    decision: str  # MATCH | NO_MATCH | ERROR
    provider_name: str
    is_mock: bool
    timestamp: datetime
    score: Optional[float] = None
    notice: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DeepfakeAssessmentResult:
    success: bool
    decision: str  # AUTHENTIC | DEEPFAKE_SUSPECTED | ERROR
    provider_name: str
    is_mock: bool
    timestamp: datetime
    risk_score: Optional[float] = None
    confidence: Optional[float] = None
    notice: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    """Abstract provider interface isolating voice biometrics & deepfake detection."""

    provider_name: str
    is_mock: bool

    @abstractmethod
    def enroll_voice(
        self,
        employee_id: int,
        audio_data: bytes,
        *,
        mime_type: str = "audio/webm",
        simulation_mode: Optional[str] = None,
    ) -> VoiceEnrollmentResult:
        """Enroll an employee voice sample."""

    @abstractmethod
    def verify_voice(
        self,
        employee_id: int,
        audio_data: bytes,
        *,
        mime_type: str = "audio/webm",
        simulation_mode: Optional[str] = None,
    ) -> VoiceVerificationResult:
        """Verify submitted voice audio against the enrolled employee profile."""

    @abstractmethod
    def detect_deepfake(
        self,
        audio_data: bytes,
        *,
        employee_id: Optional[int] = None,
        mime_type: str = "audio/webm",
        simulation_mode: Optional[str] = None,
    ) -> DeepfakeAssessmentResult:
        """Assess submitted audio for AI-generated or manipulated speech indicators."""
