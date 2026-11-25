"""SQLAlchemy ORM models for The Trust Layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utc_now
from app.db.database import Base, UTCDateTime


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    industry: Mapped[str] = mapped_column(String(120), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING", index=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    verified_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="company",
        foreign_keys="User.company_id",
        cascade="all, delete-orphan",
    )
    employees: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="company", cascade="all, delete-orphan"
    )
    communication_sessions: Mapped[list["CommunicationSession"]] = relationship(
        "CommunicationSession", back_populates="company", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    company: Mapped[Company | None] = relationship(
        "Company", back_populates="users", foreign_keys=[company_id]
    )
    employee_profile: Mapped["Employee | None"] = relationship(
        "Employee", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_code", name="uq_company_employee_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_code: Mapped[str] = mapped_column(String(100), nullable=False)
    designation: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    assigned_role: Mapped[str] = mapped_column(String(120), nullable=False)
    identity_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="COMPANY_ATTESTED"
    )
    allowed_purposes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    voice_enrolled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    user: Mapped[User] = relationship("User", back_populates="employee_profile")
    company: Mapped[Company] = relationship("Company", back_populates="employees")
    voice_enrollments: Mapped[list["VoiceEnrollment"]] = relationship(
        "VoiceEnrollment", back_populates="employee", cascade="all, delete-orphan"
    )
    communication_sessions: Mapped[list["CommunicationSession"]] = relationship(
        "CommunicationSession", back_populates="employee", cascade="all, delete-orphan"
    )


class VoiceEnrollment(Base):
    __tablename__ = "voice_enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    employee: Mapped[Employee] = relationship("Employee", back_populates="voice_enrollments")


class CommunicationSession(Base):
    __tablename__ = "communication_sessions"
    __table_args__ = (
        Index("ix_comm_session_status_expires", "status", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trust_id_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(120), nullable=False)
    reference_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    voice_verification_result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    deepfake_assessment: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE", index=True)
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    company: Mapped[Company] = relationship("Company", back_populates="communication_sessions")
    employee: Mapped[Employee] = relationship("Employee", back_populates="communication_sessions")
    customer_sessions: Mapped[list["CustomerVerificationSession"]] = relationship(
        "CustomerVerificationSession",
        back_populates="communication_session",
        cascade="all, delete-orphan",
    )
    suspicious_reports: Mapped[list["SuspiciousReport"]] = relationship(
        "SuspiciousReport",
        back_populates="communication_session",
        cascade="all, delete-orphan",
    )


class CustomerVerificationSession(Base):
    __tablename__ = "customer_verification_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    communication_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("communication_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    communication_session: Mapped[CommunicationSession] = relationship(
        "CommunicationSession", back_populates="customer_sessions"
    )


class SuspiciousReport(Base):
    __tablename__ = "suspicious_reports"
    __table_args__ = (
        UniqueConstraint(
            "communication_session_id",
            "customer_session_id",
            name="uq_report_per_customer_session",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    communication_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("communication_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_session_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("customer_verification_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN")

    communication_session: Mapped[CommunicationSession] = relationship(
        "CommunicationSession", back_populates="suspicious_reports"
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, index=True)
