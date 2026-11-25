"""Trust ID issuance, AI failure blocking, expiration, single-use & concurrency tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import select

from app.core.security import hash_token, utc_now
from app.db.models import CommunicationSession


def _setup_enrolled_employee(client, admin_headers, sample_audio_bytes):
    reg = client.post(
        "/api/companies/register",
        json={
            "company_name": "Trust Bank",
            "business_email": "sec@trustbank.example",
            "phone": "+1-555-0155",
            "industry": "Banking",
            "registration_number": "REG-TB-900",
            "password": "CompanyPass!123",
        },
    )
    cid = reg.json()["company"]["id"]
    c_token = reg.json()["access_token"]
    client.post(f"/api/admin/companies/{cid}/approve", headers=admin_headers)

    client.post(
        "/api/employees",
        headers={"Authorization": f"Bearer {c_token}"},
        json={
            "full_name": "Victor Agent",
            "email": "victor@trustbank.example",
            "employee_code": "TB-77",
            "designation": "Fraud Analyst",
            "department": "Fraud",
            "assigned_role": "Analyst",
            "allowed_purposes": ["Fraud alert", "Account verification"],
            "password": "EmpPass!123",
        },
    )
    e_token = client.post(
        "/api/auth/login",
        json={"email": "victor@trustbank.example", "password": "EmpPass!123"},
    ).json()["access_token"]

    enr = client.post(
        "/api/verification/voice-enroll",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"consent": "true"},
        files={"audio": ("enroll.webm", sample_audio_bytes, "audio/webm")},
    )
    assert enr.status_code == 200
    return e_token


def test_failed_ai_checks_prevent_trust_id_issuance(
    client, platform_admin_headers, sample_audio_bytes
):
    e_token = _setup_enrolled_employee(client, platform_admin_headers, sample_audio_bytes)

    mismatch = client.post(
        "/api/verification/pre-call",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"purpose": "Fraud alert", "simulation_mode": "voice_mismatch"},
        files={"audio": ("call.webm", sample_audio_bytes, "audio/webm")},
    )
    assert mismatch.status_code == 403
    assert mismatch.json()["issued"] is False
    assert mismatch.json()["trust_id"] is None

    deepfake = client.post(
        "/api/verification/pre-call",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"purpose": "Fraud alert", "simulation_mode": "deepfake_detected"},
        files={"audio": ("call.webm", sample_audio_bytes, "audio/webm")},
    )
    assert deepfake.status_code == 403
    assert deepfake.json()["issued"] is False
    assert deepfake.json()["trust_id"] is None


def test_valid_checks_issue_hashed_single_use_and_expiring_trust_id(
    client, db_session, platform_admin_headers, sample_audio_bytes
):
    e_token = _setup_enrolled_employee(client, platform_admin_headers, sample_audio_bytes)

    res = client.post(
        "/api/verification/pre-call",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"purpose": "Fraud alert", "reference_note": "Case #901"},
        files={"audio": ("call.webm", sample_audio_bytes, "audio/webm")},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["issued"] is True
    trust_id = body["trust_id"]
    assert trust_id.startswith("TL-")

    # Stored as hash, not plaintext
    stored = db_session.scalar(
        select(CommunicationSession).where(
            CommunicationSession.trust_id_hash == hash_token(trust_id)
        )
    )
    assert stored is not None
    assert stored.trust_id_hash != trust_id

    # Redeem once succeeds
    first = client.post("/api/public/verify", json={"trust_id": trust_id})
    assert first.status_code == 200
    assert first.json()["overall_status"] == "Verified"

    # Second redemption fails
    second = client.post("/api/public/verify", json={"trust_id": trust_id})
    assert second.status_code == 409
    assert second.json()["overall_status"] == "Invalid"

    # Issue another Trust ID and force expiry in DB -> redemption returns Expired (410)
    res2 = client.post(
        "/api/verification/pre-call",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"purpose": "Account verification"},
        files={"audio": ("call.webm", sample_audio_bytes, "audio/webm")},
    )
    tid2 = res2.json()["trust_id"]
    row2 = db_session.scalar(
        select(CommunicationSession).where(
            CommunicationSession.trust_id_hash == hash_token(tid2)
        )
    )
    row2.expires_at = utc_now() - timedelta(minutes=1)
    db_session.commit()

    exp = client.post("/api/public/verify", json={"trust_id": tid2})
    assert exp.status_code == 410
    assert exp.json()["overall_status"] == "Expired"


def test_concurrent_redemption_cannot_succeed_twice(
    app_instance, client, platform_admin_headers, sample_audio_bytes
):
    e_token = _setup_enrolled_employee(client, platform_admin_headers, sample_audio_bytes)
    res = client.post(
        "/api/verification/pre-call",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"purpose": "Fraud alert"},
        files={"audio": ("call.webm", sample_audio_bytes, "audio/webm")},
    )
    trust_id = res.json()["trust_id"]

    from fastapi.testclient import TestClient

    def _redeem():
        with TestClient(app_instance) as c:
            return c.post("/api/public/verify", json={"trust_id": trust_id}).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(lambda _: _redeem(), range(6)))

    assert codes.count(200) == 1
    assert codes.count(409) == 5
