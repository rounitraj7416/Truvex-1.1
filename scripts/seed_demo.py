"""Seed script for local development and hackathon demonstration.

Creates:
- Platform administrator (configured via SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD)
- Verified fictional company (Apex Meridian Bank) + Company Admin
- Pending fictional company (Northstar Lending Corp) + Company Admin
- Two authorized employees for Apex Meridian Bank (one voice-enrolled, one pending voice enrollment)
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password, utc_now  # noqa: E402
from app.db.database import SessionLocal, init_db  # noqa: E402
from app.db.models import Company, Employee, User, VoiceEnrollment  # noqa: E402
from app.services.audit_service import record_audit_event  # noqa: E402
from app.trust_engine.mock_provider import MockAIProvider  # noqa: E402


def seed() -> None:
    init_db()
    settings = get_settings()
    db = SessionLocal()

    try:
        admin_email = (os.getenv("SEED_ADMIN_EMAIL") or settings.SEED_ADMIN_EMAIL).strip().lower()
        admin_password = os.getenv("SEED_ADMIN_PASSWORD") or settings.SEED_ADMIN_PASSWORD
        if not admin_password:
            admin_password = secrets.token_urlsafe(14)

        company_password = os.getenv("SEED_DEMO_COMPANY_PASSWORD") or "CompanyDemo!2026"
        employee_password = os.getenv("SEED_DEMO_EMPLOYEE_PASSWORD") or "EmployeeDemo!2026"

        # 1. Platform Admin
        admin_user = db.scalar(select(User).where(User.email == admin_email))
        if not admin_user:
            admin_user = User(
                email=admin_email,
                password_hash=hash_password(admin_password),
                full_name="Platform Trust Administrator",
                role="platform_admin",
                company_id=None,
                is_active=True,
            )
            db.add(admin_user)
            db.flush()
            record_audit_event(
                db,
                actor_id=admin_user.id,
                actor_role="system",
                action="SEED_PLATFORM_ADMIN_CREATED",
                entity_type="user",
                entity_id=admin_user.id,
            )
            print(f"[SEED] Created platform_admin: {admin_email} / {admin_password}")
        else:
            print(f"[SEED] Platform admin already exists: {admin_email}")

        # 2. Verified Demo Company
        verified_email = "security@apexmeridian.example"
        apex = db.scalar(select(Company).where(Company.business_email == verified_email))
        if not apex:
            now = utc_now()
            apex = Company(
                company_name="Apex Meridian Bank",
                business_email=verified_email,
                phone="+1-800-555-0142",
                industry="Financial Services & Banking",
                registration_number="REG-FIN-2026-8841",
                verification_status="VERIFIED",
                verified_at=now,
                verified_by_id=admin_user.id,
            )
            db.add(apex)
            db.flush()

            apex_admin = User(
                email=verified_email,
                password_hash=hash_password(company_password),
                full_name="Elena Vance (CISO)",
                role="company_admin",
                company_id=apex.id,
                is_active=True,
            )
            db.add(apex_admin)
            db.flush()

            record_audit_event(
                db,
                actor_id=admin_user.id,
                actor_role="platform_admin",
                action="COMPANY_APPROVED",
                entity_type="company",
                entity_id=apex.id,
                metadata={"seeded": True, "company_name": apex.company_name},
            )
            print(f"[SEED] Created VERIFIED company_admin: {verified_email} / {company_password}")
        else:
            print(f"[SEED] Verified company already exists: {verified_email}")

        # 3. Pending Demo Company
        pending_email = "compliance@northstarlending.example"
        northstar = db.scalar(select(Company).where(Company.business_email == pending_email))
        if not northstar:
            northstar = Company(
                company_name="Northstar Lending Corp",
                business_email=pending_email,
                phone="+1-800-555-0199",
                industry="Consumer Lending",
                registration_number="REG-LND-2026-3310",
                verification_status="PENDING",
            )
            db.add(northstar)
            db.flush()

            northstar_admin = User(
                email=pending_email,
                password_hash=hash_password(company_password),
                full_name="Marcus Reed",
                role="company_admin",
                company_id=northstar.id,
                is_active=True,
            )
            db.add(northstar_admin)
            db.flush()
            record_audit_event(
                db,
                actor_id=northstar_admin.id,
                actor_role="company_admin",
                action="COMPANY_REGISTERED",
                entity_type="company",
                entity_id=northstar.id,
                metadata={"seeded": True, "company_name": northstar.company_name},
            )
            print(f"[SEED] Created PENDING company_admin: {pending_email} / {company_password}")

        # 4. Employees for Apex Meridian Bank
        emp1_email = "maya.chen@apexmeridian.example"
        emp1_user = db.scalar(select(User).where(User.email == emp1_email))
        if not emp1_user:
            emp1_user = User(
                email=emp1_email,
                password_hash=hash_password(employee_password),
                full_name="Maya Chen",
                role="employee",
                company_id=apex.id,
                is_active=True,
            )
            db.add(emp1_user)
            db.flush()

            emp1 = Employee(
                user_id=emp1_user.id,
                company_id=apex.id,
                employee_code="AMB-1042",
                designation="Senior Fraud & Verification Officer",
                department="Customer Protection",
                assigned_role="Fraud Specialist",
                identity_status="COMPANY_ATTESTED",
                allowed_purposes=["Fraud alert", "Account verification", "Loan verification"],
                voice_enrolled=True,
            )
            db.add(emp1)
            db.flush()

            mock_provider = MockAIProvider()
            mock_res = mock_provider.enroll_voice(
                emp1.id, b"SEED_CONSENTED_SYNTHETIC_DEMO_AUDIO_PAYLOAD_" * 8
            )
            enrollment = VoiceEnrollment(
                employee_id=emp1.id,
                provider=mock_res.provider_name,
                is_mock=True,
                status="ENROLLED",
                consent_given=True,
                consent_timestamp=mock_res.timestamp,
                enrolled_at=mock_res.timestamp,
                metadata_json={
                    "decision": mock_res.decision,
                    "score": mock_res.score,
                    "notice": mock_res.notice,
                    "seeded_demo": True,
                },
            )
            db.add(enrollment)
            print(f"[SEED] Created voice-enrolled employee: {emp1_email} / {employee_password}")

        emp2_email = "liam.patel@apexmeridian.example"
        emp2_user = db.scalar(select(User).where(User.email == emp2_email))
        if not emp2_user:
            emp2_user = User(
                email=emp2_email,
                password_hash=hash_password(employee_password),
                full_name="Liam Patel",
                role="employee",
                company_id=apex.id,
                is_active=True,
            )
            db.add(emp2_user)
            db.flush()

            emp2 = Employee(
                user_id=emp2_user.id,
                company_id=apex.id,
                employee_code="AMB-1088",
                designation="Loan Advisory Associate",
                department="Retail Lending",
                assigned_role="Loan Officer",
                identity_status="COMPANY_ATTESTED",
                allowed_purposes=["Loan verification", "Payment reminder"],
                voice_enrolled=False,
            )
            db.add(emp2)
            print(f"[SEED] Created unenrolled employee: {emp2_email} / {employee_password}")

        db.commit()
        print("[SEED] Demo database seeding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
