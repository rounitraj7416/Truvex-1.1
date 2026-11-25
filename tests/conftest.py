"""Pytest fixtures providing isolated SQLite database and FastAPI TestClient."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.rate_limit import rate_limiter  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.database import Base, build_engine, get_db  # noqa: E402
from app.db.models import User  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_test_ai_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def test_db_engine(tmp_path: Path):
    db_path = tmp_path / "test_trust_layer.db"
    eng = build_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(bind=eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def session_factory(test_db_engine):
    return sessionmaker(
        bind=test_db_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@pytest.fixture()
def db_session(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def app_instance(test_db_engine, session_factory, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("SECRET_KEY", "test-only-ephemeral-secret-key-at-least-32-chars")
    get_settings.cache_clear()
    rate_limiter.reset()

    app = create_app()

    def _override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield app
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
def client(app_instance) -> Generator[TestClient, None, None]:
    with TestClient(app_instance) as test_client:
        yield test_client


@pytest.fixture()
def sample_audio_bytes() -> bytes:
    return b"RIFF\x24\x08\x00\x00WAVEfmt " + b"\x01\x02\x03\x04" * 120


@pytest.fixture()
def platform_admin_headers(db_session: Session) -> dict[str, str]:
    admin = User(
        email="platform.admin@test.example",
        password_hash=hash_password("AdminPass!123"),
        full_name="Test Platform Admin",
        role="platform_admin",
        company_id=None,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    token = create_access_token(user_id=admin.id, role=admin.role, company_id=None)
    return {"Authorization": f"Bearer {token}"}
