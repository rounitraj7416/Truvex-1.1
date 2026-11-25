"""Full Phase 8 end-to-end journey test across all roles and trust layers."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_complete_end_to_end_trust_layer_journey(
    app_instance, platform_admin_headers, sample_audio_bytes
):
    with TestClient(app_instance) as company_client, TestClient(
        app_instance
    ) as employee_client, TestClient(app_instance) as customer_client:
        # 1. Company registers -> PENDING
        reg = company_client.post(
            "/api/companies/register",
            json={
                "company_name": "Horizon Trust Bank",
                "business_email": "security@horizontrust.example",
                "phone": "+1-800-555-0188",
                "industry": "Retail Banking",
                "registration_number": "REG-HTB-2026",
                "admin_full_name": "Clara Vance",
                "password": "HorizonPass!2026",
            },
        )
        assert reg.status_code == 201
        company_id = reg.json()["company"]["id"]
        assert reg.json()["company"]["verification_status"] == "PENDING"

        # 2. Platform admin approves company -> VERIFIED
        approve = company_client.post(
            f"/api/admin/companies/{company_id}/approve",
            headers=platform_admin_headers,
            json={"reason": "Verified business documents"},
        )
        assert approve.status_code == 200
        assert approve.json()["verification_status"] == "VERIFIED"

        # 3. Company creates employee
        emp_res = company_client.post(
            "/api/employees",
            json={
                "full_name": "Noah Sterling",
                "email": "noah@horizontrust.example",
                "employee_code": "HTB-204",
                "designation": "Account Protection Specialist",
                "department": "Customer Security",
                "assigned_role": "Fraud Officer",
                "allowed_purposes": ["Fraud alert", "Account verification"],
                "password": "NoahPass!2026",
            },
        )
        assert emp_res.status_code == 201

        # 4. Employee logs in
        login = employee_client.post(
            "/api/auth/login",
            json={"email": "noah@horizontrust.example", "password": "NoahPass!2026"},
        )
        assert login.status_code == 200
        assert login.json()["user"]["role"] == "employee"

        # 5. Employee enrolls voice with consent
        enroll = employee_client.post(
            "/api/verification/voice-enroll",
            data={"consent": "true"},
            files={"audio": ("enroll.webm", sample_audio_bytes, "audio/webm")},
        )
        assert enroll.status_code == 200
        assert enroll.json()["enrolled"] is True

        # 6. Employee records fresh voice sample + selects permitted purpose -> Trust ID issued
        precall = employee_client.post(
            "/api/verification/pre-call",
            data={
                "purpose": "Fraud alert",
                "reference_note": "Unusual wire transfer check",
            },
            files={"audio": ("live.webm", sample_audio_bytes, "audio/webm")},
        )
        assert precall.status_code == 201
        precall_body = precall.json()
        assert precall_body["issued"] is True
        assert precall_body["is_mock"] is True
        assert len(precall_body["layer_results"]) == 5
        assert all(lr["passed"] for lr in precall_body["layer_results"])
        trust_id = precall_body["trust_id"]

        # 7. Customer redeems Trust ID (no login required)
        verify = customer_client.post("/api/public/verify", json={"trust_id": trust_id})
        assert verify.status_code == 200
        v_body = verify.json()
        assert v_body["overall_status"] == "Verified"
        assert v_body["company"]["company_name"] == "Horizon Trust Bank"
        assert v_body["employee"]["full_name"] == "Noah Sterling"
        assert v_body["communication"]["purpose"] == "Fraud alert"
        assert v_body["ai_assessment"]["is_mock"] is True

        # 8. Customer reports suspicious activity
        report = customer_client.post(
            "/api/public/report-suspicious",
            json={
                "reason": "I did not expect this call",
                "description": "Caller requested confirmation unexpectedly.",
            },
        )
        assert report.status_code == 200
        assert report.json()["overall_status"] == "Suspicious"

        # 9. Admin sees the report and real DB statistics
        stats = company_client.get("/api/admin/stats", headers=platform_admin_headers)
        assert stats.status_code == 200
        assert stats.json()["verified_companies"] >= 1
        assert stats.json()["issued_trust_ids"] >= 1
        assert stats.json()["suspicious_reports"] >= 1

        reports = company_client.get("/api/admin/reports", headers=platform_admin_headers)
        assert reports.status_code == 200
        assert any(
            r["company_name"] == "Horizon Trust Bank"
            and r["employee_name"] == "Noah Sterling"
            and r["reason"] == "I did not expect this call"
            for r in reports.json()
        )
