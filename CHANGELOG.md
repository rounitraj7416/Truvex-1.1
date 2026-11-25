# CHANGELOG

All notable implementation decisions, assumptions, and changes for **The Trust Layer** MVP are documented in this file.

## [0.7.0] - 2026-11-25
### Render Blueprint Deployment Support
- Added [`render.yaml`](render.yaml) Blueprint configuration for deploying FastAPI + static frontend on Render (`pip install -r backend/requirements.txt`, idempotent `seed_demo.py` on boot, `/api/health` health check, `COOKIE_SECURE=true`, auto-generated `SECRET_KEY`).
- Added `https://*.onrender.com` CORS origin regex support in [`backend/app/main.py`](backend/app/main.py).

## [0.6.0] - 2026-11-25
### Interactive & Animated README
- Designed animated SVG architecture banners ([`docs/assets/trust-layer-banner.svg`](docs/assets/trust-layer-banner.svg) and [`docs/assets/five-gate-pipeline.svg`](docs/assets/five-gate-pipeline.svg)) with `prefers-reduced-motion` fallbacks.
- Rebuilt [`README.md`](README.md) with native GitHub Mermaid sequence diagram, collapsible `<details>` accordions for the Five Trust Layers, API endpoints, demo credentials, DetectifAI configuration, security controls, and verified screenshots.

## [0.5.0] - 2026-11-25
### DetectifAI Aletheia + Eidos Integration & Audio File Upload UI
- Implemented [`DetectifAIProvider`](file:///c:/Users/rouni/Documents/Truvex/backend/app/trust_engine/detectifai_provider.py) against official `https://platform.detectif.ai` REST endpoints (`POST /v1/speakers/enroll`, `POST /v1/speakers/verify`, `POST /v1/deepfake/detect`) using `Authorization: Bearer` and per-request `Idempotency-Key` headers.
- Added local audio file upload pickers (`.wav`, `.mp3`, `.webm`, `.ogg`, `.m4a`, `.flac`, `.aac`) with playback preview alongside the `MediaRecorder` microphone capture on [`employee-dashboard.html`](file:///c:/Users/rouni/Documents/Truvex/frontend/employee-dashboard.html), [`recorder.js`](file:///c:/Users/rouni/Documents/Truvex/frontend/js/recorder.js), and [`employee.js`](file:///c:/Users/rouni/Documents/Truvex/frontend/js/employee.js).
- Added unit tests for `DetectifAIProvider` request/response parsing and `.wav` octet-stream fallback in [`tests/test_ai_provider.py`](file:///c:/Users/rouni/Documents/Truvex/tests/test_ai_provider.py).

## [0.4.0] - 2026-11-25
### Bespoke Architectural Redesign & Five-Gate Clearinghouse Set-Piece
- Replaced the dark-navy/neon-cyan SaaS-card layout with a custom **Architectural Bond & Clearinghouse Cobalt** token system (`#F4F5F2` paper, `#E9ECE6` ledger, `#141A21` carbon ink, `#1649FF` cobalt, `#0D6E4E` emerald) and crisp 1px structural rules in [`styles.css`](file:///c:/Users/rouni/Documents/Truvex/frontend/css/styles.css).
- Built a pinned `320vh` scroll-choreographed **Five-Gate Clearinghouse** centerpiece in [`index.html`](file:///c:/Users/rouni/Documents/Truvex/frontend/index.html) and [`motion.js`](file:///c:/Users/rouni/Documents/Truvex/frontend/js/motion.js) using compositor-only `transform` updates (`requestAnimationFrame` + sticky pinning, zero scroll-jacking), locking Gates 01–05 sequentially until minting a sample Trust ID, with a full static vertical fallback under `prefers-reduced-motion: reduce`.
- Added a live 5-minute TTL specimen countdown in the hero and a subtle supported-mandates ticker strip while keeping inner dashboards and `/verify.html` aligned to the unified token system.

## [0.3.0] - 2026-11-25
### Section 10.1 — Scroll Animations & Interactive UI Polish
- Added [`frontend/js/motion.js`](file:///c:/Users/rouni/Documents/Truvex/frontend/js/motion.js) using native `IntersectionObserver`, `requestAnimationFrame` stat counters, and scroll-linked vertical timeline progress (`#how-timeline`), progressively enhanced (`js-motion`) so all content stays visible if JS fails or `prefers-reduced-motion: reduce` is active.
- Upgraded [`frontend/index.html`](file:///c:/Users/rouni/Documents/Truvex/frontend/index.html) into a 7-section narrative (Hero with animated Trust Pipeline illustration & metrics, Problem threats, Solution call-verification diagram, 5 Trust Layers grid, How It Works vertical timeline, Security & Trust engineering, and Final CTA).
- Added restrained dashboard entrance, tab transition, button/card hover, modal entrance, and smooth toast enter/exit micro-interactions in [`frontend/css/styles.css`](file:///c:/Users/rouni/Documents/Truvex/frontend/css/styles.css), [`api.js`](file:///c:/Users/rouni/Documents/Truvex/frontend/js/api.js), [`admin.js`](file:///c:/Users/rouni/Documents/Truvex/frontend/js/admin.js), and [`company.js`](file:///c:/Users/rouni/Documents/Truvex/frontend/js/company.js).

## [0.2.0] - 2026-11-25
### Phases 1–8 — Full Backend, Frontend, Seeding & Automated Test Suite
- **Core & Database:** Implemented `Settings`, Argon2id password hashing, PyJWT auth tokens, `TL-XXXX-XXXX-XXXX-XXXX` high-entropy Trust ID generator, SHA-256 token hashing, SQLite WAL engine with `UTCDateTime` decorator, and sliding-window rate limiter.
- **Five Independent Trust Layers:** Implemented `business_verification.py`, `employee_verification.py`, `trust_engine/` (`AIProvider`, `MockAIProvider`, `DetectifAIProvider`, `factory.py`), `permission_verification.py`, `session_service.py`, and central `verification_orchestrator.py`.
- **Atomic Single-Use Redemption:** Executed conditional `UPDATE ... WHERE status='ACTIVE' AND revoked_at IS NULL AND expires_at > :now` as the first write statement in SQLite transactions to prevent concurrent double-redemption, followed by `HttpOnly` anonymous customer verification session cookies.
- **API & Frontend:** Built FastAPI routers (`auth`, `companies`, `employees`, `verification`, `public`, `admin`) and plain HTML/CSS/Vanilla JS screens (`index.html`, `company-register.html`, `login.html`, `company-dashboard.html`, `employee-dashboard.html`, `verify.html`, `admin-dashboard.html`) with native `MediaRecorder` audio capture & preview.
- **Seed & Tests:** Added `scripts/seed_demo.py`, `README.md`, and 18 automated pytest cases covering RBAC, company isolation, consent, mock honesty, AI failure blocking, concurrency, expiration, suspicious reporting, rate limiting, and full E2E flow.
- **Browser Verification Fixes:** Fixed `FRONTEND_DIR` path resolution in `backend/app/main.py` (`parents[2]`), added `[hidden] { display: none !important; }` in `frontend/css/styles.css` so `.grid-2` detail cards stay hidden on `Invalid`/`Expired` Trust IDs, and wrapped employee table action buttons cleanly on narrower viewports.
