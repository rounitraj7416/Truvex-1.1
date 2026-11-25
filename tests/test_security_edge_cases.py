"""Security edge-case tests: rate limiting, oversized audio, and company suspension blocking."""

from __future__ import annotations

from app.core.config import get_settings


def test_public_verify_rate_limit_enforced(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_RATE_LIMIT_PER_MINUTE", "3")
    get_settings.cache_clear()
    try:
        for _ in range(3):
            res = client.post("/api/public/verify", json={"trust_id": "TL-AAAA-BBBB-CCCC-DDDD"})
            assert res.status_code == 404

        blocked = client.post("/api/public/verify", json={"trust_id": "TL-AAAA-BBBB-CCCC-DDDD"})
        assert blocked.status_code == 429
    finally:
        get_settings.cache_clear()


def test_oversized_audio_rejected(client, platform_admin_headers, sample_audio_bytes, monkeypatch):
    monkeypatch.setenv("MAX_AUDIO_UPLOAD_BYTES", "500")
    get_settings.cache_clear()
    try:
        reg = client.post(
            "/api/companies/register",
            json={
                "company_name": "Size Check Co",
                "business_email": "sec@sizecheck.example",
                "phone": "+1-555-0122",
                "industry": "Tech",
                "registration_number": "REG-SIZE-1",
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
                "full_name": "Size Tester",
                "email": "size@sizecheck.example",
                "employee_code": "SZ-1",
                "designation": "Agent",
                "department": "Ops",
                "assigned_role": "Agent",
                "allowed_purposes": ["Customer support"],
                "password": "EmpPass!123",
            },
        )
        e_token = client.post(
            "/api/auth/login",
            json={"email": "size@sizecheck.example", "password": "EmpPass!123"},
        ).json()["access_token"]

        oversized = b"A" * 800
        res = client.post(
            "/api/verification/voice-enroll",
            headers={"Authorization": f"Bearer {e_token}"},
            data={"consent": "true"},
            files={"audio": ("big.webm", oversized, "audio/webm")},
        )
        assert res.status_code == 413
    finally:
        get_settings.cache_clear()


def test_suspended_company_blocks_precall_trust_id(
    client, platform_admin_headers, sample_audio_bytes
):
    reg = client.post(
        "/api/companies/register",
        json={
            "company_name": "Suspend Check Bank",
            "business_email": "sec@suspendbank.example",
            "phone": "+1-555-0144",
            "industry": "Banking",
            "registration_number": "REG-SUSP-1",
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
            "full_name": "Sam Caller",
            "email": "sam@suspendbank.example",
            "employee_code": "SB-1",
            "designation": "Advisor",
            "department": "Support",
            "assigned_role": "Advisor",
            "allowed_purposes": ["Customer support"],
            "password": "EmpPass!123",
        },
    )
    e_token = client.post(
        "/api/auth/login",
        json={"email": "sam@suspendbank.example", "password": "EmpPass!123"},
    ).json()["access_token"]

    client.post(
        "/api/verification/voice-enroll",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"consent": "true"},
        files={"audio": ("e.webm", sample_audio_bytes, "audio/webm")},
    )

    # Suspend company
    susp = client.post(
        f"/api/admin/companies/{cid}/suspend",
        headers=platform_admin_headers,
        json={"reason": "Audit hold"},
    )
    assert susp.status_code == 200

    # Pre-call check must fail Layer 1
    precall = client.post(
        "/api/verification/pre-call",
        headers={"Authorization": f"Bearer {e_token}"},
        data={"purpose": "Customer support"},
        files={"audio": ("p.webm", sample_audio_bytes, "audio/webm")},
    )
    assert precall.status_code == 403
    assert precall.json()["issued"] is False
    assert precall.json()["layer_results"][0]["passed"] is False
    assert precall.json()["layer_results"][0]["status"] == "SUSPENDED"
