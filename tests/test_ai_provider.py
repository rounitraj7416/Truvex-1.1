"""AI provider abstraction, mock honesty disclosures, DetectifAI adapter, consent, and upload tests."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import get_settings
from app.trust_engine.ai_provider import MOCK_NOTICE, ProviderConfigurationError
from app.trust_engine.detectifai_provider import DetectifAIProvider
from app.trust_engine.factory import get_ai_provider


def test_mock_provider_identifies_itself_and_is_deterministic(sample_audio_bytes):
    provider = get_ai_provider()
    assert provider.is_mock is True

    enroll = provider.enroll_voice(42, sample_audio_bytes)
    assert enroll.success is True
    assert enroll.is_mock is True
    assert enroll.notice == MOCK_NOTICE

    v1 = provider.verify_voice(42, sample_audio_bytes)
    v2 = provider.verify_voice(42, sample_audio_bytes)
    assert v1.score == v2.score
    assert v1.is_mock is True
    assert v1.notice == MOCK_NOTICE

    df = provider.detect_deepfake(sample_audio_bytes, employee_id=42)
    assert df.success is True
    assert df.is_mock is True
    assert df.notice == MOCK_NOTICE


def test_detectifai_unconfigured_raises_clear_error(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "detectifai")
    monkeypatch.setenv("DETECTIFAI_API_BASE_URL", "")
    monkeypatch.setenv("DETECTIFAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(ProviderConfigurationError) as exc:
            get_ai_provider()
        assert "not configured" in str(exc.value).lower()
    finally:
        get_settings.cache_clear()


def test_detectifai_provider_calls_official_endpoints(monkeypatch, sample_audio_bytes):
    monkeypatch.setenv("AI_PROVIDER", "detectifai")
    monkeypatch.setenv("DETECTIFAI_API_BASE_URL", "https://platform.detectif.ai")
    monkeypatch.setenv("DETECTIFAI_API_KEY", "dtf_test_dummy_key")
    get_settings.cache_clear()

    seen_requests: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(
            (request.method, request.url.path, request.headers.get("authorization"))
        )
        assert request.headers.get("idempotency-key")
        if request.url.path == "/v1/speakers/enroll":
            return httpx.Response(
                200,
                json={
                    "request_id": "req_enroll_1",
                    "object": "speaker.enrollment",
                    "speaker_id": "emp-7",
                    "status": "enrolled",
                    "samples_count": 1,
                    "duration_seconds": 6.2,
                },
            )
        if request.url.path == "/v1/speakers/verify":
            return httpx.Response(
                200,
                json={
                    "request_id": "req_verify_1",
                    "object": "speaker.verification",
                    "speaker_id": "emp-7",
                    "result": {"decision": "match", "similarity": 0.91, "duration_seconds": 5.0},
                },
            )
        if request.url.path == "/v1/deepfake/detect":
            return httpx.Response(
                200,
                json={
                    "request_id": "req_df_1",
                    "operation_id": "op_df_1",
                    "object": "deepfake.detection",
                    "result": {"verdict": "real", "score": 0.04, "duration_seconds": 5.0},
                },
            )
        return httpx.Response(404, json={"error": {"code": "not_found", "message": "missing"}})

    transport = httpx.MockTransport(handler)
    orig_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)
    try:
        provider = get_ai_provider()
        assert isinstance(provider, DetectifAIProvider)
        assert provider.is_mock is False

        e_res = provider.enroll_voice(7, sample_audio_bytes, mime_type="audio/wav")
        assert e_res.success is True
        assert e_res.is_mock is False
        assert e_res.metadata["request_id"] == "req_enroll_1"

        v_res = provider.verify_voice(7, sample_audio_bytes, mime_type="audio/wav")
        assert v_res.success is True
        assert v_res.decision == "MATCH"
        assert v_res.score == 0.91

        d_res = provider.detect_deepfake(sample_audio_bytes, employee_id=7, mime_type="audio/wav")
        assert d_res.success is True
        assert d_res.decision == "AUTHENTIC"
        assert d_res.risk_score == 0.04

        assert [p for _, p, _ in seen_requests] == [
            "/v1/speakers/enroll",
            "/v1/speakers/verify",
            "/v1/deepfake/detect",
        ]
        assert all(auth == "Bearer dtf_test_dummy_key" for _, _, auth in seen_requests)
    finally:
        get_settings.cache_clear()


def test_voice_enrollment_requires_consent_and_valid_audio(
    client, platform_admin_headers, sample_audio_bytes
):
    reg = client.post(
        "/api/companies/register",
        json={
            "company_name": "Consent Co",
            "business_email": "sec@consent.example",
            "phone": "+1-555-0133",
            "industry": "Insurance",
            "registration_number": "REG-CONSENT-1",
            "password": "CompanyPass!123",
        },
    )
    cid = reg.json()["company"]["id"]
    c_token = reg.json()["access_token"]
    client.post(f"/api/admin/companies/{cid}/approve", headers=platform_admin_headers)

    client.post(
        "/api/employees",
        headers={"Authorization": f"Bearer {c_token}"},
        json={
            "full_name": "Consent Tester",
            "email": "tester@consent.example",
            "employee_code": "C-01",
            "designation": "Advisor",
            "department": "Claims",
            "assigned_role": "Advisor",
            "allowed_purposes": ["Policy renewal"],
            "password": "EmpPass!123",
        },
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "tester@consent.example", "password": "EmpPass!123"},
    )
    e_token = login.json()["access_token"]

    # Missing consent fails
    no_consent = client.post(
        "/api/verification/voice-enroll",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"consent": "false"},
        files={"audio": ("voice.webm", sample_audio_bytes, "audio/webm")},
    )
    assert no_consent.status_code == 400

    # Invalid file type fails
    bad_mime = client.post(
        "/api/verification/voice-enroll",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"consent": "true"},
        files={"audio": ("malware.exe", b"MZ" * 100, "application/x-msdownload")},
    )
    assert bad_mime.status_code == 400

    # Valid .wav file upload with application/octet-stream fallback succeeds
    ok = client.post(
        "/api/verification/voice-enroll",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"consent": "true"},
        files={"audio": ("voice.wav", sample_audio_bytes, "application/octet-stream")},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["enrolled"] is True
    assert body["is_mock"] is True
    assert "DEMO MODE" in body["mock_notice"]
