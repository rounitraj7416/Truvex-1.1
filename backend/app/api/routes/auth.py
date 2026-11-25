"""Authentication routes: login, logout, and current user summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.database import get_db
from app.db.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserSummary
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _build_user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        company_id=user.company_id,
        company_name=user.company.company_name if user.company else None,
        company_status=user.company.verification_status if user.company else None,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate a platform admin, company admin, or employee."""
    email_norm = payload.email.strip().lower()
    user = db.scalar(
        select(User).options(joinedload(User.company)).where(User.email == email_norm)
    )
    if not user or not verify_password(payload.password, user.password_hash):
        record_audit_event(
            db,
            actor_id=user.id if user else None,
            actor_role=user.role if user else "anonymous",
            action="LOGIN_FAILED",
            entity_type="user",
            entity_id=user.id if user else None,
            metadata={"email": email_norm},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )

    token = create_access_token(
        user_id=user.id, role=user.role, company_id=user.company_id
    )
    settings = get_settings()
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )

    record_audit_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="LOGIN_SUCCESS",
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()

    return TokenResponse(access_token=token, user=_build_user_summary(user))


@router.post("/logout")
def logout(response: Response):
    """Clear the authentication cookie."""
    settings = get_settings()
    response.delete_cookie(key=settings.AUTH_COOKIE_NAME, path="/")
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserSummary)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return authenticated user profile and company status."""
    user = db.scalar(
        select(User).options(joinedload(User.company)).where(User.id == current_user.id)
    )
    assert user is not None
    return _build_user_summary(user)
