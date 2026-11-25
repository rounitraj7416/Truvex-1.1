"""Public customer verification and suspicious activity reporting routes."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import enforce_public_rate_limit
from app.db.database import get_db
from app.schemas.verification import (
    SUSPICIOUS_REASONS,
    PublicVerificationResponse,
    PublicVerifyRequest,
    SuspiciousReportRequest,
    SuspiciousReportResponse,
)
from app.services.session_service import (
    get_customer_session_verification,
    redeem_trust_id_atomically,
    submit_suspicious_report,
)

router = APIRouter(prefix="/api/public", tags=["Public Verification"])


@router.get("/reasons")
def get_suspicious_reasons():
    """Return allowed suspicious report reasons for customer reporting UI."""
    return {"reasons": SUSPICIOUS_REASONS}


@router.post(
    "/verify",
    response_model=PublicVerificationResponse,
    dependencies=[Depends(enforce_public_rate_limit)],
)
def verify_trust_id(
    payload: PublicVerifyRequest,
    db: Session = Depends(get_db),
):
    """Redeem a single-use Trust ID atomically and set an anonymous customer session cookie."""
    verification_res, raw_session_key, status_code = redeem_trust_id_atomically(
        db, payload.trust_id
    )
    json_resp = JSONResponse(
        status_code=status_code,
        content=verification_res.model_dump(mode="json"),
    )
    if raw_session_key:
        settings = get_settings()
        json_resp.set_cookie(
            key=settings.CUSTOMER_SESSION_COOKIE_NAME,
            value=raw_session_key,
            httponly=True,
            samesite="lax",
            secure=settings.COOKIE_SECURE,
            max_age=settings.CUSTOMER_SESSION_EXPIRY_MINUTES * 60,
            path="/",
        )
    return json_resp


@router.get("/session", response_model=PublicVerificationResponse)
def get_current_customer_session(
    customer_session: str | None = Cookie(
        default=None, alias="trust_layer_customer_session"
    ),
    db: Session = Depends(get_db),
):
    """Retrieve the active anonymous customer verification session without re-redeeming Trust ID."""
    if not customer_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active verification session.",
        )

    res, state = get_customer_session_verification(db, customer_session)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification session not found or revoked.",
        )
    if state == "expired":
        return JSONResponse(status_code=410, content=res.model_dump(mode="json"))
    return res


@router.post("/session/clear")
def clear_customer_session(response: Response):
    """Clear the anonymous customer session cookie so the customer can verify a new ID."""
    settings = get_settings()
    response.delete_cookie(key=settings.CUSTOMER_SESSION_COOKIE_NAME, path="/")
    return {"cleared": True}


@router.post(
    "/report-suspicious",
    response_model=SuspiciousReportResponse,
    dependencies=[Depends(enforce_public_rate_limit)],
)
def report_suspicious_session(
    payload: SuspiciousReportRequest,
    customer_session: str | None = Cookie(
        default=None, alias="trust_layer_customer_session"
    ),
    db: Session = Depends(get_db),
):
    """Submit a suspicious communication report from an active customer session."""
    if not customer_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verify a Trust ID first before submitting a suspicious report.",
        )

    try:
        return submit_suspicious_report(
            db,
            raw_session_key=customer_session,
            reason=payload.reason,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
