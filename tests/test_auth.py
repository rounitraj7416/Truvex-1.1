"""Authentication and RBAC tests."""

from __future__ import annotations

from app.core.security import hash_password
from app.db.models import User


def test_login_and_me_flow(client, db_session):
    user = User(
        email="admin.login@test.example",
        password_hash=hash_password("StrongPass!2026"),
        full_name="Login Admin",
        role="platform_admin",
        company_id=None,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    bad = client.post(
        "/api/auth/login",
        json={"email": "admin.login@test.example", "password": "wrong"},
    )
    assert bad.status_code == 401

    ok = client.post(
        "/api/auth/login",
        json={"email": "admin.login@test.example", "password": "StrongPass!2026"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["user"]["role"] == "platform_admin"
    assert "trust_layer_auth" in ok.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "admin.login@test.example"

    out = client.post("/api/auth/logout")
    assert out.status_code == 200


def test_unauthenticated_access_rejected(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/admin/stats").status_code == 401
    assert client.get("/api/employees").status_code == 401


def test_frontend_pages_served(client):
    for path in ("/", "/login.html", "/company-register.html", "/verify.html", "/css/styles.css", "/js/api.js", "/js/motion.js"):
        res = client.get(path)
        assert res.status_code == 200, f"Expected 200 for {path}, got {res.status_code}"

