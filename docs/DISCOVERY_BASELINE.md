# ClearNum / NumberShield — Discovery & Engineering Baseline Report
**Document ID**: `docs/DISCOVERY_BASELINE.md`  
**Date**: October 27, 2026  
**Auditor**: Principal Privacy & Software Architecture Lead  
**Repository**: [https://github.com/JeyaVardhan-L/ClearNum.git](https://github.com/JeyaVardhan-L/ClearNum.git) (`main` @ `58fa101`)

---

## 1. Executive Baseline & Verification Summary

This document establishes the verified empirical baseline of the ClearNum codebase prior to Phase 1–6 enhancements. Every assertion in this report was verified through direct command execution, network tracing, and code analysis.

### Repository Status
- **Git Branch**: `main` (tracked to `origin/main` at commit `58fa101`).
- **Working Tree**: Clean (0 uncommitted changes).
- **Safety Checkpoints**: Local branch `backup-pre-audit` and annotated tag `checkpoint-pre-audit` preserved.
- **Operating Mode**: 100% Free, zero mandatory paid APIs, zero commercial proxies, strictly localhost-bound (`127.0.0.1:8765`).

---

## 2. Test Suite & Build Verification

### A. Backend Pytest Suite
- **Command**: `.venv\Scripts\pytest -v`
- **Result**: **64 passed, 1 warning, 0 failed** in 56.05s
- **Warning**: `StarletteDeprecationWarning` in FastAPI testclient (`httpx` import).

| Test Module | Tests | Status | Scope Verified |
| :--- | :--- | :--- | :--- |
| `tests/test_api.py` | 10 | PASSED | Health, phone parse, dorks, broker directory, legal notice templates, synthetic demo, purge, scan deduplication, transition 400 rejection, and forensic export. |
| `tests/test_e2e_playwright.py` | 2 | PASSED | Live desktop (1440x900) and mobile (390x844) viewport navigation, synthetic demo loading, dorks modal, CCPA letter generation, spam incident logging, syndicate clustering, and cryptographic purge. |
| `tests/test_lifecycle.py` | 4 | PASSED | Truthful lifecycle state machine transitions, rejection from discovered, prevention of premature removal claims, arbitrary transition denial. |
| `tests/test_local_parsers.py` | 2 | PASSED | MBOX email unsubscribe extraction, Android SMS backup XML parsing and shortcode grouping. |
| `tests/test_matcher.py` | 5 | PASSED | Exact phone match, probable match, false-positive date rejection, false-positive UUID rejection, script/style HTML tag stripping. |
| `tests/test_normalizer.py` | 16 | PASSED | Telephony normalization across 10 countries (US, GB, IN, DE, FR, JP, AU, CA, BR, SG), invalid number rejection, search variant generation. |
| `tests/test_privacy_redactor.py` | 4 | PASSED | Masking format (`+1 ••• ••• •• 71`), 256-bit keyed HMAC stability/uniqueness, log scrubbing, cryptographic database purge. |
| `tests/test_remediation_registry.py` | 9 | PASSED | Broker domain lookups (FastPeopleSearch, TruePeopleSearch, Whitepages, Radaris, Spokeo, Nuwber, GitHub, Pastebin) and 25+ broker count. |
| `tests/test_ssrf.py` | 12 | PASSED | SSRF boundary rejection (loopback `127.0.0.1`, RFC 1918 `10.x`, `172.16.x`, `192.168.x`, cloud metadata `169.254.169.254`, `file://`, `gopher://`, `ftp://`). |

### B. Frontend Verification
- **Linter**: `npm run lint` (`oxlint`) passed with 4 minor code quality warnings:
  - `src/App.tsx:35:16`: Unused error parameter in catch block.
  - `src/components/PreventionView.tsx:48:5`: `refreshData` called in `useEffect` prior to definition.
  - `src/components/ScanConsole.tsx:58:16`: Unused error parameter in catch block.
- **Production Build**: `tsc -b && vite build` succeeded in 17.45s.
  - Distribution: `frontend/dist/index.html` (0.45 kB), `index-KKTpxbnJ.css` (3.81 kB), `index-DX_cpX55.js` (314.33 kB).
  - Mounted automatically at FastAPI root `/` and `/assets`.

### C. Playwright E2E Test Execution Reality
- **Mocking Status**: **ZERO MOCKS**.
- The test harness (`tests/test_e2e_playwright.py`) launches a background thread running `uvicorn.Server` on `127.0.0.1:8766`.
- Headless Chromium connects over HTTP to the real server, retrieves the compiled React bundle, executes API calls (`POST /api/demo/synthetic`, `GET /api/discovery/exposures`, `POST /api/prevention/incidents`, `POST /api/privacy/purge`), and validates real DOM updates.

---

## 3. Empirical Discovery Adapter Audit

Every discovery mechanism was tested live to separate working capabilities from limitations:

```
+----------------------------------------------------------------------------------------------------+
|                                    DISCOVERY CAPABILITY SPECTRUM                                   |
+----------------------------------------------------------------------------------------------------+
| 1. Live Automated Search    | DuckDuckGo HTML (Working, 7 results) | SearXNG Public (Failing, 429) |
| 2. Public Target Adapter    | safe_fetch_url with SSRF check (Working)                             |
| 3. Manual Query Generator   | 1-Click Search Dorks across 15+ search engines (Working, 100%)       |
| 4. User-Provided Data       | Local MBOX & SMS XML/JSON Parsers (Working, 100% Offline)            |
| 5. Synthetic Demonstration  | Offline Realistic Demo Fixtures (Working)                            |
+----------------------------------------------------------------------------------------------------+
```

### A. DuckDuckGo HTML Provider (`backend/app/engines/discovery/providers/duckduckgo.py`)
- **Direct Live Test Command**:
  ```python
  res = asyncio.run(DuckDuckGoProvider().search(parse_and_normalize('+14155552671')))
  ```
- **Empirical Result**: **7 live public exposure records returned**.
  - `https://www.tellows.com/num/%2B14155552671`
  - `https://www.tellows.com/num/4155552671`
  - `https://support.hushed.com/hc/en-us/articles/360015706691-Making-Calls-How-do-I-make-a-call-with-a-Hushed-number`
  - `https://scamora.com/phone/%2B14155552671`
  - `https://us.shouldianswer.net/phone-number/4155552671`
  - `https://support.google.com/adsense/answer/2938681?hl=en`
  - `https://spamcalls.net/fr/num/14155552671`
- **Gaps & Defects Identified**:
  1. **Single-Format Query Limitation**: The provider only queries `f'"{phone.e164}"'`. It misses pages that display numbers as `(415) 555-2671`, `415-555-2671`, or `+1 415 555 2671`.
  2. **Unicode Glyph Crash on Windows**: Certain page titles contained telephone emoji `\u260e`, triggering `UnicodeEncodeError` on Windows consoles with `cp1252` encoding.
  3. **Rate Limiting**: Rapid consecutive searches can trigger DDG's bot detection (HTTP 202 or 403).

### B. SearXNG Meta-Search Provider (`backend/app/engines/discovery/providers/searxng.py`)
- **Direct Live Test Command**: Tested individual public instances from `FALLBACK_INSTANCES`.
- **Empirical Results**:
  - `https://priv.au/search`: Returned **HTTP 429** (Rate Limited).
  - `https://search.ononoki.org/search`: Failed with **ConnectError** (Domain unreachable).
  - `https://searx.tiekoetter.com/search`: Returned **HTTP 429** (Rate Limited).
- **Gaps & Defects Identified**:
  1. Public SearXNG instances disable or aggressively throttle JSON format endpoints (`/search?format=json`) to prevent scraper abuse.
  2. **Silent Failure**: When public SearXNG instances fail, the provider caught the exception and returned `[]`, silently hiding the failure from the user.
  3. **Mitigation Needed**: Expose provider health and error status in the API, and guide users to connect an optional local Docker SearXNG instance (`http://localhost:8080`).

### C. Direct Browser Search Dorks (`backend/app/engines/discovery/providers/manual_dorks.py`)
- **Empirical Result**: **100% Reliable**.
- Generates 15 pre-formatted URLs covering Google, Bing, Brave, Yahoo, Yandex, GitHub Code Search, Pastebin, FastPeopleSearch, TruePeopleSearch, Whitepages, Radaris, Spokeo, Craigslist, and Yelp.
- **Zero Risk**: Bypasses anti-scraping and CAPTCHA walls because searches execute interactively in the user's browser session.

### D. User-Authorized Local Parsers
- **MBOX Parser (`mbox_parser.py`)**: Parses standard RFC 822 / MIME email archives in local memory. Successfully extracts `List-Unsubscribe` headers (both `mailto:` and `https://` URLs) and checks for phone exposures.
- **SMS Parser (`sms_parser.py`)**: Analyzes XML/JSON/CSV backups from Android SMS backup apps. Identifies commercial shortcodes (4–6 digits), marketing keyword patterns, and `STOP` commands.
- **Privacy Guarantee**: Zero network egress. Files are processed in memory and temporary files are unlinked in `finally` blocks.

---

## 4. Remediation & Verification State Audit

### State Machine Analysis
The current implementation enforces an 11-state transition model in `lifecycle.py`:
- `DISCOVERED` -> `VERIFIED` or `REJECTED`
- `VERIFIED` -> `ACTION_AVAILABLE`, `MANUAL_ACTION_REQUIRED`, `REJECTED`
- `ACTION_AVAILABLE` -> `SUBMITTED`, `MANUAL_ACTION_REQUIRED`, `REJECTED`
- `SUBMITTED` -> `ACKNOWLEDGED`, `PENDING`, `VERIFIED_REMOVED`, `FAILED`, `UNABLE_TO_VERIFY`, `REJECTED`
- `ACKNOWLEDGED` -> `PENDING`, `VERIFIED_REMOVED`, `FAILED`, `UNABLE_TO_VERIFY`, `REJECTED`
- `PENDING` -> `VERIFIED_REMOVED`, `FAILED`, `UNABLE_TO_VERIFY`, `SUBMITTED`, `REJECTED`

### Gaps vs. Truthful Remediation Requirements
1. **Premature Removal vs. URL Non-Availability**: An HTTP 404 or 410 on an exposure URL means "Page is currently not found on this URL." It does **not** prove that the underlying data broker deleted the record from their offline database.
2. **Missing Granular States**: The state machine needs explicit distinctions:
   - `AWAITING_USER_APPROVAL`: User has generated a notice but hasn't approved sending/submitting.
   - `URL_NO_LONGER_VISIBLE`: Live HTTP 404/410 check passed.
   - `SOURCE_CONFIRMED_REMOVAL`: Positive confirmation received from broker (confirmation email or ticket ID).
   - `SEARCH_ENGINE_DELISTED`: Search snippet removed via Google/Bing outdated content tool.
   - `REAPPEARED`: Re-scanned and detected anew after earlier removal.

---

## 5. Security & Privacy Audit

### A. Keyed HMAC & Data Isolation
- Raw phone numbers are **never persisted** in SQLite.
- Identities are indexed exclusively by 256-bit keyed HMAC-SHA256 (`identity_hmac`), derived from `data/.numbershield_key`.
- Key file has strict owner permissions (`0600` on POSIX).
- In UI and logs, numbers are masked to `+1 ••• ••• •• 71`.

### B. SSRF Defenses & DNS Rebinding Vulnerability
- Current protection in `backend/app/core/ssrf.py`:
  - `validate_url_safe()` resolves hostname via `socket.getaddrinfo()` and rejects loopback (`127.0.0.0/8`), link-local/cloud metadata (`169.254.169.254`), and private subnets (`10.x`, `172.16.x`, `192.168.x`).
  - Redirect hops are re-validated up to 5 times.
- **Architectural Vulnerability Identified (TOCTOU DNS Rebinding)**:
  - `validate_url_safe(url)` validates IP addresses at time $T_0$.
  - `client.get(current_url)` in `httpx` executes a second, independent DNS resolution at connection time $T_1$.
  - An attacker-controlled DNS server can return a safe public IP at $T_0$, then return `127.0.0.1` or `169.254.169.254` at $T_1$.
  - **Remediation Required**: Implement an `SSRFProtectedTransport` that pins the validated IP address directly during the HTTP socket connection.

### C. Cryptographic Purge Limitations
- `purge_all_data()` drops all SQLite tables, runs `VACUUM`, wipes `.numbershield_key` with random bytes, and zeroes WAL files.
- **Truthful Documentation Reality**: On solid-state drives (SSDs) with wear-leveling algorithms, user-space byte overwriting does not guarantee physical block erasure. This must be disclosed honestly in `docs/privacy.md`.

---

## 6. Actionable Implementation Priorities

Based on the empirical baseline findings, the recommended engineering priorities for Phases 1–6 are:

1. **Phase 1 & 2: Pluggable Discovery Engine with Bounded Retries & Format Permutations**:
   - Upgrade query generator to search international, national, dashed, and spaced variants (`+14155552671`, `(415) 555-2671`, `415-555-2671`).
   - Implement structured provider health reporting: if SearXNG returns HTTP 429, report "Provider throttled / unconfigured" rather than silent empty results.
   - Add safe public code/document search adapters (e.g. GitHub public code search queries, Pastebin raw search dorks).
2. **Phase 3: Explainable Entity Resolution & Corpus Benchmark**:
   - Enhance `matcher.py` to differentiate between:
     - Direct personal contact listing vs. documentation example/test fixture (e.g., `555-0199`).
     - Presence of corroborating identity tokens (user's name, city, state).
   - Establish a reproducible benchmark corpus measuring precision, recall, and false-positive rates across synthetic and public test cases.
3. **Phase 4: Granular, Truthful Remediation State Machine**:
   - Expand `ActionState` to distinguish `URL_NO_LONGER_VISIBLE` (HTTP 404) from `SOURCE_CONFIRMED_REMOVAL` (broker affirmative confirmation).
   - Add states for `AWAITING_USER_APPROVAL`, `SEARCH_ENGINE_DELISTED`, and `REAPPEARED`.
4. **Phase 5: Layered Connection-Pinned SSRF Transport**:
   - Implement `SSRFProtectedTransport` in `httpx` that enforces socket-level IP binding to close the DNS rebinding TOCTOU window.
5. **Phase 6: Quality, Linter Polish & Documentation**:
   - Resolve the 4 oxlint warnings in `App.tsx`, `ScanConsole.tsx`, and `PreventionView.tsx`.
   - Update `SOURCE_CAPABILITY_MATRIX.md`, `RESEARCH_DECISIONS.md`, and `THREAT_MODEL.md`.
