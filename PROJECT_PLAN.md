# PROJECT PLAN — THE TRUST LAYER

## 1. Objective
Build **The Trust Layer**, an AI-powered business communication verification platform (MVP) that enables verified companies to register employees, enroll employee voices, run 5-layer pre-call verification checks, issue cryptographically random single-use Trust IDs, and allow customers to independently verify communications or report suspicious activity without creating an account.

## 2. Architecture & Five Independent Trust Layers
1. **Layer 1 — Business Verification** (`backend/app/services/business_verification.py`): Verifies that the company exists and is in `VERIFIED` status (not `PENDING`, `REJECTED`, or `SUSPENDED`).
2. **Layer 2 — Employee Identity Verification** (`backend/app/services/employee_verification.py`): Verifies employee authentication, active user status, matching company association, and `COMPANY_ATTESTED` identity status.
3. **Layer 3 — AI Voice & Deepfake Verification** (`backend/app/trust_engine/`): Isolated provider interface (`ai_provider.py`), deterministic configurable `MockAIProvider` (`mock_provider.py`), and explicitly unconfigured `DetectifAIProvider` adapter (`detectifai_provider.py`). Enforces explicit consent for enrollment and outputs structured voice-match and deepfake assessment metadata with mandatory mock disclosure when simulated.
4. **Layer 4 — Authority & Permission Verification** (`backend/app/services/permission_verification.py`): Verifies that the selected communication purpose is explicitly permitted in the employee's `allowed_purposes` list.
5. **Layer 5 — Communication Session Validity** (`backend/app/services/session_service.py`): Generates high-entropy Trust IDs (`TL-XXXX-XXXX-XXXX-XXXX`), stores SHA-256 hashes, enforces configurable UTC expiry (default 5 minutes), executes atomic single-use redemption via SQLite conditional updates, issues `HttpOnly` anonymous customer verification session cookies, and handles suspicious reporting & revocation.

A central orchestration service (`backend/app/services/verification_orchestrator.py`) executes Layers 1–5 in sequence and refuses Trust ID issuance if any mandatory check fails.

## 3. Repository Structure
```text
Truvex/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── dependencies.py
│   │   │   └── rate_limit.py
│   │   ├── db/
│   │   │   ├── database.py
│   │   │   └── models.py
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── company.py
│   │   │   ├── employee.py
│   │   │   ├── verification.py
│   │   │   └── admin.py
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── auth.py
│   │   │       ├── companies.py
│   │   │       ├── employees.py
│   │   │       ├── verification.py
│   │   │       ├── public.py
│   │   │       └── admin.py
│   │   ├── services/
│   │   │   ├── audit_service.py
│   │   │   ├── business_verification.py
│   │   │   ├── employee_verification.py
│   │   │   ├── permission_verification.py
│   │   │   ├── session_service.py
│   │   │   └── verification_orchestrator.py
│   │   └── trust_engine/
│   │       ├── ai_provider.py
│   │       ├── mock_provider.py
│   │       ├── detectifai_provider.py
│   │       └── factory.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── company-register.html
│   ├── login.html
│   ├── company-dashboard.html
│   ├── employee-dashboard.html
│   ├── verify.html
│   ├── admin-dashboard.html
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── api.js
│       ├── auth.js
│       ├── company.js
│       ├── employee.js
│       ├── recorder.js
│       ├── verification.js
│       └── admin.js
├── scripts/
│   └── seed_demo.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_companies.py
│   ├── test_employees.py
│   ├── test_ai_provider.py
│   ├── test_trust_sessions.py
│   ├── test_public_verification.py
│   └── test_e2e_flow.py
├── artifacts/
│   └── screenshots/
├── README.md
├── CHANGELOG.md
├── PROJECT_PLAN.md
├── AGENTS.md
├── .gitignore
└── .env.example
```

## 4. Database Relationships
- `Company` 1──* `User` (company admins and employees)
- `Company` 1──* `Employee`
- `User` 1──1 `Employee` (for users with `role='employee'`)
- `Employee` 1──* `VoiceEnrollment` (metadata only, no raw audio stored)
- `Company` 1──* `CommunicationSession`
- `Employee` 1──* `CommunicationSession`
- `CommunicationSession` 1──* `CustomerVerificationSession`
- `CommunicationSession` 1──* `SuspiciousReport`
- `AuditLog` records all security-sensitive actions across entities.

## 5. Phased Execution
- Phase 0: Inspection & planning (done)
- Phase 1: Project scaffolding & dependency installation
- Phase 2: Auth & company registration/approval workflow
- Phase 3: Employee management & permission enforcement
- Phase 4: AI provider abstraction, mock provider, and voice enrollment
- Phase 5: 5-layer verification orchestration & atomic Trust ID issuance/redemption
- Phase 6: Public customer verification & suspicious reporting UI/API
- Phase 7: Platform admin console & audit logs
- Phase 8: Full integration testing, pytest suite, browser verification & screenshots
