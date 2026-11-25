"""Employee creation, isolation, activation, and purpose authorization tests."""

from __future__ import annotations


def _create_verified_company(client, admin_headers, email, reg, name):
    reg_res = client.post(
        "/api/companies/register",
        json={
            "company_name": name,
            "business_email": email,
            "phone": "+1-555-0111",
            "industry": "FinTech",
            "registration_number": reg,
            "password": "CompanyPass!123",
        },
    )
    assert reg_res.status_code == 201
    cid = reg_res.json()["company"]["id"]
    token = reg_res.json()["access_token"]
    app_res = client.post(f"/api/admin/companies/{cid}/approve", headers=admin_headers)
    assert app_res.status_code == 200
    return cid, token


def test_employee_company_isolation_and_permissions(
    client, platform_admin_headers, sample_audio_bytes
):
    cid_a, token_a = _create_verified_company(
        client, platform_admin_headers, "a@compa.example", "REG-A-100", "Company A"
    )
    _cid_b, token_b = _create_verified_company(
        client, platform_admin_headers, "b@compb.example", "REG-B-200", "Company B"
    )

    # Create employee in Company A
    emp_res = client.post(
        "/api/employees",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "full_name": "Alice Agent",
            "email": "alice@compa.example",
            "employee_code": "A-001",
            "designation": "Loan Officer",
            "department": "Loans",
            "assigned_role": "Loan Officer",
            "allowed_purposes": ["Loan verification"],
            "password": "EmpPass!123",
        },
    )
    assert emp_res.status_code == 201
    emp = emp_res.json()
    assert emp["company_id"] == cid_a

    # Company B cannot view or edit Company A's employee
    b_list = client.get("/api/employees", headers={"Authorization": f"Bearer {token_b}"})
    assert b_list.status_code == 200
    assert b_list.json() == []

    b_patch = client.patch(
        f"/api/employees/{emp['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"designation": "Hijacked"},
    )
    assert b_patch.status_code == 404

    # Employee logs in
    emp_login = client.post(
        "/api/auth/login",
        json={"email": "alice@compa.example", "password": "EmpPass!123"},
    )
    assert emp_login.status_code == 200
    emp_token = emp_login.json()["access_token"]

    # Enroll voice
    enroll = client.post(
        "/api/verification/voice-enroll",
        headers={"Authorization": f"Bearer {emp_token}"},
        data={"consent": "true"},
        files={"audio": ("sample.webm", sample_audio_bytes, "audio/webm")},
    )
    assert enroll.status_code == 200

    # Unapproved communication purpose is rejected (Layer 4)
    unapproved = client.post(
        "/api/verification/pre-call",
        headers={"Authorization": f"Bearer {emp_token}"},
        data={"purpose": "Fraud alert"},
        files={"audio": ("sample.webm", sample_audio_bytes, "audio/webm")},
    )
    assert unapproved.status_code == 403
    assert unapproved.json()["issued"] is False
    assert any(
        lr["layer"].startswith("Layer 4") and not lr["passed"]
        for lr in unapproved.json()["layer_results"]
    )

    # Deactivate employee -> cannot log in or generate Trust IDs
    deact = client.patch(
        f"/api/employees/{emp['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"is_active": False},
    )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    # Existing employee token is rejected because user is inactive
    blocked = client.post(
        "/api/verification/pre-call",
        headers={"Authorization": f"Bearer {emp_token}"},
        data={"purpose": "Loan verification"},
        files={"audio": ("sample.webm", sample_audio_bytes, "audio/webm")},
    )
    assert blocked.status_code == 401
