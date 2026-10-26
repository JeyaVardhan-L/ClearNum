# AGENTS.md — Development Invariants & Guidelines for NumberShield

Welcome to the NumberShield codebase. This document outlines mandatory architectural invariants, security rules, and engineering practices that every agent or developer MUST follow when contributing to or maintaining NumberShield.

---

## 1. Core Philosophies & Inviolable Rules

1. **Zero Mandatory Cost**:
   - NumberShield must NEVER introduce mandatory paid APIs, commercial subscriptions, paid LLMs, or cloud-hosted requirements.
   - All discovery, parsing, legal template generation, and verification workflows must remain fully functional on a standalone local machine.

2. **Strict Localhost Binding**:
   - The FastAPI backend and any services must bind exclusively to `127.0.0.1` (never `0.0.0.0`).
   - The application does not collect or transmit telemetry, user metrics, or tracking pings to any external server.

3. **Cryptographic Privacy Isolation**:
   - **Never store raw phone numbers** in the database or log files.
   - User identities are indexed solely by a 256-bit keyed HMAC-SHA256 (`identity_hmac`), derived from `.numbershield_key`.
   - In UI and terminal outputs, phone numbers must always be formatted using `mask_phone_number()` (e.g., `+1 ••• ••• •• 71`).
   - Logging and error handlers must always run through `backend/app/core/redactor.py`.

4. **SSRF Hardening**:
   - Any feature that makes outbound HTTP requests (such as live URL verification) MUST enforce SSRF protection via `validate_outbound_url()` or `SSRFProtectedTransport`.
   - Outbound requests must reject:
     - Loopback (`127.0.0.0/8`, `::1`)
     - Private subnets (RFC 1918: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
     - Link-local and cloud metadata (`169.254.169.254`, `fe80::/10`)
     - Non-HTTP/HTTPS schemes (`file://`, `gopher://`, `ftp://`).

5. **Truthful Lifecycle State Machine**:
   - NumberShield must NEVER display simulated, misleading, or premature claims of data deletion.
   - All exposure status updates must validate against `can_transition(current, target)` in `backend/app/engines/remediation/lifecycle.py`.
   - Transition to `VERIFIED_REMOVED` requires affirmative verification (e.g. live HTTP 404/410 check or explicit confirmation code).

6. **Cryptographic Zero-Trace Purge**:
   - The `/api/privacy/purge` endpoint and CLI `numbershield purge` command must execute `purge_all_data()`, which wipes SQLite tables, unlinks `.numbershield_key`, and clears in-memory structures.

---

## 2. Directory Layout & Key Modules

```
ClearNum/
├── backend/app/
│   ├── core/
│   │   ├── config.py             # Settings, paths, port 8765, localhost defaults
│   │   ├── security.py           # HMAC-SHA256, 256-bit key seed, masking, memory wiping
│   │   ├── ssrf.py               # Strict DNS & IP network boundary filter
│   │   ├── redactor.py           # Universal regex phone digit scrub for logs
│   │   └── database.py           # SQLite in WAL mode, schema definitions, purge_all_data
│   ├── engines/
│   │   ├── discovery/
│   │   │   ├── normalizer.py     # libphonenumber normalizer across 10+ countries
│   │   │   ├── matcher.py        # Exact/probable matcher, date & UUID false positive rejection
│   │   │   ├── providers/        # SearXNG, DuckDuckGo, Manual Dork generator
│   │   │   └── local_parsers/    # MBOX email parser, Android SMS XML backup parser
│   │   ├── remediation/
│   │   │   ├── registry.py       # 25+ curated data broker directory
│   │   │   ├── lifecycle.py      # Truthful state transitions and validations
│   │   │   ├── templates.py      # CCPA, GDPR, TCPA, TRAI, Merchant statutory notices
│   │   │   ├── search_removal.py # Google & Bing PII delisting workflows
│   │   │   └── dnd_guides.py     # US, UK, IN, CA, AU telecom guides & carrier 7726
│   │   └── prevention/
│   │       ├── incident_tracker.py # Spam incident logging
│   │       ├── campaign_analyzer.py# Syndicate clustering by topic and spoof patterns
│   │       ├── verifier.py       # SSRF-safe live HTTP verification
│   │       └── metrics.py        # Truthful before/after metrics
│   ├── api/
│   │   ├── schemas.py            # Pydantic v2 request/response models
│   │   └── routes.py             # FastAPI REST endpoints
│   ├── cli/
│   │   └── main.py               # Typer & Rich CLI entrypoints
│   └── main.py                   # FastAPI app entrypoint, mounts frontend/dist
├── frontend/
│   ├── src/
│   │   ├── api.ts                # API client with origin-relative (/api) endpoints
│   │   ├── types.ts              # Clean TypeScript interfaces
│   │   ├── index.css             # Dark security theme (design-taste-frontend compliant)
│   │   ├── App.tsx               # Main layout and tab orchestrator
│   │   └── components/
│   │       ├── Navbar.tsx        # Responsive header with identity badge & quick actions
│   │       ├── ScanConsole.tsx   # Normalizer, dork generator, active providers
│   │       ├── ExposuresView.tsx # Exposure audit table, verification, state modal
│   │       ├── RemediationHub.tsx# Broker directory, legal notice generator, delisting
│   │       ├── PreventionView.tsx# Spam logging, syndicates, recent log, DND guides
│   │       └── VerificationAudit.tsx # MBOX/SMS imports, metrics, forensic audit export
├── docs/                         # Architecture, Privacy, Security, Threat Model docs
└── tests/                        # 61+ automated unit, integration, and Playwright tests
```

---

## 3. Frontend Standards

- **Theme & Aesthetic**: Follow `design-taste-frontend` guidelines. Use dark mode slate/zinc palette (`#090d16` background, `#0f172a` panels, `#1e293b` borders).
- **Typography**: Inter / Outfit sans-serif for UI copy; JetBrains Mono / SF Mono for phone numbers, HMAC IDs, URLs, and code snippets.
- **Dense, High-Information Displays**: Prefer compact, high-contrast tables and cards over empty whitespace or oversized landing-page cards.
- **Relative API Calls**: Always use `API_BASE = import.meta.env.VITE_API_URL || "/api"` so the app runs identically behind any port or proxy.
- **Build Verification**: Run `npm run build` after editing frontend components to ensure zero TypeScript or bundling errors.

---

## 4. Testing Standards

Always execute the complete test suite before submitting changes:
```bash
# Run backend unit, integration, and browser tests
.venv/Scripts/pytest -v

# Run only Playwright e2e browser tests
.venv/Scripts/pytest -v tests/test_e2e_playwright.py
```

### Invariants for Tests:
- Ensure database isolation: call `purge_all_data()` before tests that verify exact record counts.
- In Playwright tests, prefer `page.wait_for_selector()` over bare `is_visible()` checks to accommodate React asynchronous render updates.
- Scope selectors properly (e.g. `page.locator("nav").locator(...)` or `.first`) to avoid Playwright strict mode violations.
