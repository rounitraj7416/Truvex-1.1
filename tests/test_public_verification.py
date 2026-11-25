"""Public customer verification session, privacy, suspicious reporting, and audit tests."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.security import utc_now
from app.db.models import CustomerVerificationSession


def test_public_session_persistence_privacy_and_suspicious_reporting(
    client, db_session, platform_admin_headers, sample_audio_bytes
):
    reg = client.post(
        "/api/companies/register",
        json={
            "company_name": "Meridian Credit",
            "business_email": "sec@meridian.example",
            "phone": "+1-555-0177",
            "industry": "Credit Services",
            "registration_number": "REG-MC-501",
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
            "full_name": "Elena Caller",
            "email": "elena@meridian.example",
            "employee_code": "MC-999",
            "designation": "Collections Lead",
            "department": "Billing",
            "assigned_role": "Lead",
            "allowed_purposes": ["Payment reminder"],
            "password": "EmpPass!123",
        },
    )
    e_token = client.post(
        "/api/auth/login",
        json={"email": "elena@meridian.example", "password": "EmpPass!123"},
    ).json()["access_token"]

    client.post(
        "/api/verification/voice-enroll",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"consent": "true"},
        files={"audio": ("e.webm", sample_audio_bytes, "audio/webm")},
    )
    issue = client.post(
        "/api/verification/pre-call",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"purpose": "Payment reminder"},
        files={"audio": ("p.webm", sample_audio_bytes, "audio/webm")},
    )
    trust_id = issue.json()["trust_id"]

    # Customer redeems Trust ID
    redeem = client.post("/api/public/verify", json={"trust_id": trust_id})
    assert redeem.status_code == 200
    payload = redeem.json()
    assert payload["overall_status"] == "Verified"
    assert "trust_layer_customer_session" in redeem.cookies

    # Ensure sensitive internals are NOT exposed on public response
    raw_text = redeem.text
    assert "elena@meridian.example" not in raw_text
    assert "MC-999" not in raw_text
    assert "password_hash" not in raw_text

    # Customer refreshes page -> GET /api/public/session works without Trust ID re-redemption
    refresh = client.get("/api/public/session")
    assert refresh.status_code == 200
    assert refresh.json()["company"]["company_name"] == "Meridian Credit"

    # Submit suspicious report
    rep = client.post(
        "/api/public/report-suspicious",
        json={
            "reason": "Suspicious voice",
            "description": "Voice sounded robotic and pressured me for OTP.",
        },
    )
    assert rep.status_code == 200
    assert rep.json()["reported"] is True
    assert rep.json()["overall_status"] == "Suspicious"

    # Duplicate report from same customer session is rejected
    dup = client.post(
        "/api/public/report-suspicious",
        json={"reason": "Other", "description": "Duplicate attempt"},
    )
    assert dup.status_code == 409

    # Refreshing customer session now reflects Suspicious overall status
    after_rep = client.get("/api/public/session")
    assert after_rep.status_code == 200
    assert after_rep.json()["overall_status"] == "Suspicious"
    assert after_rep.json()["suspicious_reported"] is True

    # Admin sees suspicious report and audit event
    reports = client.get("/api/admin/reports", headers=platform_admin_headers)
    assert reports.status_code == 200
    assert len(reports.json()) == 1
    assert reports.json()[0]["reason"] == "Suspicious voice"

    audits = client.get("/api/admin/audit-logs", headers=platform_admin_headers)
    assert audits.status_code == 200
    actions = [a["action"] for a in audits.json()]
    assert "TRUST_ID_ISSUED" in actions
    assert "TRUST_ID_REDEEMED" in actions
    assert "SUSPICIOUS_REPORT_SUBMITTED" in actions

    # Expire customer session -> /api/public/session returns 410
    cust_row = db_session.scalar(select(CustomerVerificationSession))
    cust_row.expires_at = utc_now() - timedelta(minutes=1)
    db_session.commit()
    expired_session = client.get("/api/public/session")
    assert expired_session.status_code == 410
