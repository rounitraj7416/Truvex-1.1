# AGENTS.md — The Trust Layer

## Project Conventions
- **Stack**: Python 3 + FastAPI + SQLAlchemy 2.x + SQLite + Pydantic v2; Frontend is plain HTML/CSS/Vanilla JS served by FastAPI.
- **No Frameworks**: Do not introduce React, Vue, Next.js, or Tailwind build pipelines.
- **Five Trust Layers**: Keep Business Verification, Employee Identity Verification, AI Voice/Deepfake Verification (`trust_engine/`), Permission Verification, and Communication Session Validity as separate modules orchestrated by `verification_orchestrator.py`.
- **Honesty**: Mock AI provider results must always set `is_mock=True` and clearly surface `DEMO MODE` notices in logs, DB, API responses, and UI. Never present mock output as real acoustic analysis.
- **Security**: Never commit `.env` or secrets. Never store raw audio or plaintext Trust IDs in the database. Enforce all authorization on the backend.
- **Testing**: Keep `pytest` suite green in `tests/` and update `CHANGELOG.md` on meaningful changes.
