"""Company registration, admin approval, suspension, and RBAC tests."""

from __future__ import annotations


def _register_sample_company(client, email="ops@alpha.example", reg="REG-ALPHA-1"):
    return client.post(
        "/api/companies/register",
        json={
            "company_name": "Alpha Bank",
            "business_email": email,
            "phone": "+1-555-0100",
            "industry": "Banking",
            "registration_number": reg,
            "admin_full_name": "Alpha Admin",
            "password": "CompanyPass!123",
        },
    )


def test_company_registration_creates_pending_status(client):
    res = _register_sample_company(client)
    assert res.status_code == 201
    data = res.json()
    assert data["company"]["verification_status"] == "PENDING"
    token = data["access_token"]

    # Pending company cannot register active authorized employees
    emp_res = client.post(
        "/api/employees",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "Blocked Employee",
            "email": "emp@alpha.example",
            "employee_code": "EMP-1",
            "designation": "Agent",
            "department": "Support",
            "assigned_role": "Support Agent",
            "allowed_purposes": ["Customer support"],
            "password": "EmpPass!123",
        },
    )
    assert emp_res.status_code == 403


def test_unauthorized_user_cannot_access_admin_endpoints(client):
    reg = _register_sample_company(client, email="nonadmin@beta.example", reg="REG-BETA-1")
    token = reg.json()["access_token"]

    assert (
        client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/admin/companies/1/approve",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 403
    )


def test_admin_can_approve_reject_suspend_reactivate_company(client, platform_admin_headers):
    reg = _register_sample_company(client, email="verify@gamma.example", reg="REG-GAMMA-1")
    company_id = reg.json()["company"]["id"]

    # Approve
    approved = client.post(
        f"/api/admin/companies/{company_id}/approve",
        headers=platform_admin_headers,
        json={"reason": "Verified registration"},
    )
    assert approved.status_code == 200
    assert approved.json()["verification_status"] == "VERIFIED"
    assert approved.json()["verified_at"] is not None

    # Suspend
    suspended = client.post(
        f"/api/admin/companies/{company_id}/suspend",
        headers=platform_admin_headers,
        json={"reason": "Compliance review"},
    )
    assert suspended.status_code == 200
    assert suspended.json()["verification_status"] == "SUSPENDED"

    # Reactivate
    reactivated = client.post(
        f"/api/admin/companies/{company_id}/reactivate",
        headers=platform_admin_headers,
        json={},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["verification_status"] == "VERIFIED"

    # History recorded
    history = client.get(
        f"/api/admin/companies/{company_id}/history",
        headers=platform_admin_headers,
    )
    assert history.status_code == 200
    actions = [h["action"] for h in history.json()["history"]]
    assert "COMPANY_REGISTERED" in actions
    assert "COMPANY_APPROVED" in actions
    assert "COMPANY_SUSPENDED" in actions
    assert "COMPANY_REACTIVATED" in actions

    # Reject a second company
    reg2 = _register_sample_company(client, email="rej@delta.example", reg="REG-DELTA-1")
    cid2 = reg2.json()["company"]["id"]
    rejected = client.post(
        f"/api/admin/companies/{cid2}/reject",
        headers=platform_admin_headers,
        json={"reason": "Invalid registration identifier"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["verification_status"] == "REJECTED"
    assert rejected.json()["rejection_reason"] == "Invalid registration identifier"
