"""Main FastAPI application serving API routes and static frontend assets."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, auth, companies, employees, public, verification
from app.core.config import get_settings
from app.db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    init_db()
    logger.info(
        "Started %s (env=%s, ai_provider=%s)",
        settings.APP_NAME,
        settings.ENVIRONMENT,
        settings.AI_PROVIDER,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="The Trust Layer API",
        description=(
            "AI-Powered Business Communication Verification Platform (Track 03 MVP). "
            "Verifies company legitimacy, employee identity, AI voice/deepfake signals, "
            "communication authority, and single-use Trust ID sessions."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception):
        logger.exception("Unhandled server error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected internal error occurred."},
        )

    @app.get("/api/health", tags=["Health"])
    def health_check():
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "ai_provider": settings.AI_PROVIDER,
            "is_mock_ai": settings.AI_PROVIDER.lower() == "mock",
        }

    app.include_router(auth.router)
    app.include_router(companies.router)
    app.include_router(employees.router)
    app.include_router(verification.router)
    app.include_router(public.router)
    app.include_router(admin.router)

    if FRONTEND_DIR.exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

        @app.get("/", include_in_schema=False)
        def serve_index():
            return FileResponse(str(FRONTEND_DIR / "index.html"))

        @app.get("/{page_name}.html", include_in_schema=False)
        def serve_html_page(page_name: str):
            target = (FRONTEND_DIR / f"{page_name}.html").resolve()
            if target.parent != FRONTEND_DIR.resolve() or not target.is_file():
                return JSONResponse(status_code=404, content={"detail": "Page not found."})
            return FileResponse(str(target))

        @app.get("/verify", include_in_schema=False)
        def serve_verify_alias():
            return FileResponse(str(FRONTEND_DIR / "verify.html"))

    return app


app = create_app()
