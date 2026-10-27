# Independent Engineering Review and Discovery Validation Report

**Product**: ClearNum / NumberShield  
**Branch**: `feature/secure-measurable-discovery`  
**Review Date**: October 27, 2026  
**Review Type**: Independent Engineering Audit & Adversarial Validation  
**Operating Mode**: Zero Mandatory Cost • Cryptographic Privacy Isolation • Strict Localhost  

---

## 1. Executive Summary

This independent engineering review audited the ClearNum discovery engine, network security posture, benchmark claims, and remediation lifecycle. 

The previous sprint reported 110 passing backend tests, 2 passing Playwright tests, zero frontend lint warnings, a successful production build, socket-level SSRF connection pinning, a 14-case discovery benchmark reporting 100% accuracy, and new Wikimedia and Hacker News adapters.

### Summary of Verdicts:
1. **SSRF Protections (Partially Verified -> Hardened to Fully Verified)**:
   - While `SSRFSafeNetworkBackend` pinned TCP sockets in `safe_fetch_url`, **discovery search adapters (`searxng`, `duckduckgo`, `wikimedia`, `hackernews`) were vulnerable** because they bypassed `SSRFSafeTransport` and used bare `httpx.AsyncClient` instances with `follow_redirects=True` or `trust_env=True`. Furthermore, destination ports were unrestricted, permitting SSRF against non-web services (e.g., Redis on 6379, SMTP on 25).
   - **Remediation**: Closed all provider SSRF bypasses by standardizing all search adapters on `SSRFSafeTransport(verify=True, follow_redirects=False, trust_env=False)` and enforcing `PERMITTED_WEB_PORTS = {80, 443, 8080, 8443}`.
2. **Benchmark Claims (Clarified & Expanded)**:
   - The reported 100% accuracy on the 14-case benchmark was **strictly an in-memory string and pattern matching test**, not an internet-wide recall metric. The duplicate rate metric was hardcoded against a single test fixture.
   - **Remediation**: Decomposed the benchmark into four distinct, measurable suites (Normalization, Content Matching, Provider Adapter Parsing, and E2E Pipeline Deduplication). Expanded the evaluation corpus from 14 to 22 cases with adversarial vectors (off-by-one near-misses, fullwidth Unicode digits, HTML entity encoding, multi-number decoy documents, discussion quotes, 404 tombstones, and ambiguous foreign numbers).
3. **Remediation Lifecycle & Audit Trail (Defect Closed)**:
   - Although the `action_audit_log` SQLite table was defined, neither the state transition API endpoint nor the automated verifier engine actually wrote audit records.
   - **Remediation**: Implemented immutable cryptographic audit trail insertion on every state change, indexed solely by `identity_hmac` with affirmative evidence classification, and exposed the audit log in forensic exports.
4. **Provider-Health Transparency (Hardened)**:
   - Partial or total search provider failure (e.g. public SearXNG rate-limiting) was previously masked by the UI, which displayed "Scan complete: 0 exposures".
   - **Remediation**: Added `scan_status` (`complete`, `partial_failure`, `all_failed`) across the API and UI to truthfully communicate provider degradation.
5. **Quality Gates Passed**:
   - Backend unit and integration tests: **132 passed** (up from 110).
   - Playwright E2E browser tests: **2 passed**.
   - Frontend linting (`oxlint`): **0 warnings, 0 errors**.
   - Frontend production build (`tsc -b && vite build`): **Clean bundle (0 errors)**.
   - `git diff --check`: **0 whitespace/conflict errors**.

---

## 2. Findings Ranked by Severity

| ID | Severity | Component | Finding Description | Status |
|---|---|---|---|---|
| **SEC-01** | **Critical** | Discovery Providers | SearXNG, DuckDuckGo, Wikimedia, and Hacker News adapters used standard `httpx.AsyncClient` rather than `SSRFSafeTransport`. In `searxng.py`, `follow_redirects=True` allowed a rogue/compromised instance to redirect the local agent to `127.0.0.1:8765/api/privacy/purge` or cloud metadata. | **RESOLVED** |
| **SEC-02** | **High** | SSRF Core | `validate_url_safe` did not validate outbound TCP ports, allowing connections to internal services on ports 22, 25, 6379, 11211, or 9200. | **RESOLVED** |
| **REM-01** | **High** | Remediation / Audit | `action_audit_log` table was never populated during state transitions or verification checks, violating forensic non-repudiation and auditability requirements. | **RESOLVED** |
| **BENCH-01**| **Medium** | Discovery Benchmark | Reported "100% accuracy" conflated in-memory document matching with search recall; duplicate rate was hardcoded binary logic (`0.0 if m.matched else 1.0`). | **RESOLVED** |
| **OBS-01**  | **Medium** | Scan Engine / UI | Search scan reported "Scan complete: 0 exposures found" even when all external providers were blocked by HTTP 429 rate limits or network errors. | **RESOLVED** |
| **ROB-01**  | **Medium** | Discovery Matcher | Matcher failed on HTML entity-encoded numbers (`&#43;1-415...`) and East Asian fullwidth Unicode digits (`＋１４１５５５５２６７１`). | **RESOLVED** |
| **SSRF-03** | **Low** | SSRF Fetcher | Streaming fetcher could theoretically hang if a malicious server streamed bytes infinitesimally slowly below chunk timeouts. | **RESOLVED** |

---

## 3. Workstream Validation & Proofs

### Workstream 1 — Git & Integration State
- **Branch**: `feature/secure-measurable-discovery`
- **HEAD Commit (Baseline)**: `eefff37` (*"docs: add discovery baseline and hardening notes"*)
- **Reported Commits Verified Locally**:
  1. `c540441`: chore(deps): upgrade dependencies and setup testing
  2. `4ae6752`: feat: add search providers and audit verification
  3. `537d4e2`: feat: enhance provider health and audit controls
  4. `eefff37`: docs: add discovery baseline and hardening notes
- **Remote Tracking**: `origin` is set to `https://github.com/JeyaVardhan-L/ClearNum.git`. The feature branch is local-only; no unapproved pushes were made.
- **Main Branch**: Untouched at `58fa101`.
- **Database Initialization & Migrations**: Verified against both a fresh database and a legacy database with deprecated status strings (`VERIFIED`, `ACTION_AVAILABLE`, `PENDING`, `VERIFIED_REMOVED`, `UNABLE_TO_VERIFY`, `FAILED`). All records migrated cleanly to truthful states via `init_db()`.

### Workstream 2 — SSRF Audit & Hardening
- **Socket Destination Pinning**: Proven via `test_ssrf_backend_pins_socket_destination_to_ip`. The network backend intercepts `connect_tcp`, resolves and validates DNS against all forbidden ranges, and instructs the underlying socket to connect directly to the pinned IP string (e.g., `"93.184.216.34"`), completely eliminating DNS rebinding TOCTOU windows.
- **Port Boundary Filter**: Enforced `PERMITTED_WEB_PORTS = {80, 443, 8080, 8443}`. Tested against ports 22, 25, 6379, 11211, and 9200; all rejected with `SSRFValidationError`.
- **Redirect Revalidation**: `safe_fetch_url` uses `follow_redirects=False`. Redirect hops (301, 302, 303, 307, 308) are caught, re-validated through `validate_url_safe`, and capped at 5 hops. Tested redirect chains targeting private IP `127.0.0.1:8000/internal`; rejected at hop 1.
- **Decompression Bomb Protection**: Tested via `test_safe_fetch_url_guards_against_decompression_bomb`. When streaming decompressed content, byte iteration terminates and raises `SSRFValidationError` once the uncompressed byte threshold is crossed.
- **Streaming Elapsed Timeout**: Added overall wall-clock elapsed stream deadline. Proven via `test_safe_fetch_url_enforces_streaming_timeout`.
- **Environment Isolation**: SSRFSafeTransport enforces `trust_env=False`, preventing HTTP_PROXY/HTTPS_PROXY environment variables from hijacking or bypassing the pinned network backend.

### Workstream 3 — Discovery Benchmark Audit
- **Scope Clarification**: The benchmark evaluates **in-memory text matching and negative-control filtering on standardized document fixtures**. It does not measure internet-wide crawl recall or search engine index freshness.
- **Modular Suites**:
  1. `run_normalization_benchmark()`: Evaluates E.164 conversion, national formats, dashed/spaced variants, area code extraction, and query permutation generation across US, GB, IN, FR, DE, JP, AU, and invalid inputs.
  2. `run_matching_benchmark()`: Evaluates 22 ground-truth document fixtures. Precision: 100%, Recall: 100%, F1: 1.0, FPR: 0.0%, Multi-Mention Duplicate Residual: 0.0%.
  3. `run_provider_benchmark()`: Tests adapter parsing and status mapping across healthy responses, HTTP 429 rate limits, and network errors.
  4. `run_e2e_pipeline_benchmark()`: Measures duplicate elimination across multi-provider injection (40% duplicate reduction rate).
- **Corpus Expansion (14 -> 22 Cases)**:
  - `eval_15_off_by_one_near_miss`: Verifies that a similar number differing by one digit (`415-555-2672` vs `415-555-2671`) is rejected.
  - `eval_16_multiple_numbers_in_doc`: Verifies target number extraction when multiple decoy numbers exist on the page.
  - `eval_17_unicode_fullwidth_digits`: Verifies extraction of Japanese/Chinese fullwidth digits (`＋１４１５５５５２６７１`).
  - `eval_18_discussion_quote_context`: Verifies matching in quoted markdown/email discussions.
  - `eval_19_nanp_reserved_test_number`: Verifies matching on reserved fictional test numbers (`555-0199`).
  - `eval_20_html_entity_encoded`: Verifies matching when phone numbers are obfuscated with decimal HTML entities (`&#43;1&#45;415...`).
  - `eval_21_stale_404_page_negative`: Verifies that standard 404 pages containing no phone numbers are classified as negative controls.
  - `eval_22_ambiguous_regional_different_country`: Verifies that foreign numbers with identical local digits but different country codes (+33) are rejected.

### Workstream 4 — Real Contribution of Each Source

| Provider | Corpus / Index Searched | Automation Mode | Auth & Cost | Observed Availability & Rate Limits | Privacy Impact | Incremental Yield |
|---|---|---|---|---|---|---|
| **DuckDuckGo** | General web index (HTML portal) | Automated | Free, No Auth | Prone to HTTP 429 and anti-bot challenges on rapid queries | Sends quoted E.164 query to DuckDuckGo servers | High on general web leaks, paste dumps, and directory profiles |
| **SearXNG** | Meta-search aggregating Google, Bing, Qwant | Automated | Free, No Auth | Public instances heavily rate-limited; self-hosted required for reliability | Sends query to selected SearXNG instance | Aggregates multiple search engines without commercial API keys |
| **Wikimedia** | Wikipedia & Wikimedia Commons content, talk pages, revision histories | Automated | Free, No Auth (Descriptive UA) | Highly available, reliable, zero observed rate-limits | Sends query to Wikimedia Foundation API | High on public biographies, notable persons, community talk pages, leaked staff profiles |
| **Hacker News** | Algolia HN index (stories, comments, profiles, Show HN) | Automated | Free, No Auth | Highly available, generous unauthenticated tier | Sends query to Algolia HN search API | High on tech worker profiles, "Who's Hiring" comments, resumes, and code launch threads |
| **Manual Dorks** | Google, Bing, Brave, Yandex, FastPeopleSearch, That'sThem, Radaris, Whitepages, Spokeo | User-Mediated (1-Click) | Free, No Auth | 100% available; user completes search in own browser | Queries originate directly from user browser session | Highest real-world yield; completely bypasses server-side scraping blockers and CAPTCHAs |

### Workstream 5 — Provider-Health Propagation
- In `backend/app/api/schemas.py`, added `scan_status` (`complete`, `partial_failure`, `all_failed`).
- In `backend/app/api/routes.py`, `scan_status` is computed from the health of all queried providers:
  - If all providers succeed: `complete`.
  - If some providers encounter rate-limits or timeouts: `partial_failure`.
  - If all providers fail: `all_failed`.
- In `frontend/src/components/ScanConsole.tsx`, truthful messaging alerts the user if rate-limiting or network errors occurred, directing them to provider diagnostics rather than falsely claiming 0 exposures.
- Verified safe diagnostics: diagnostics display masked representations (e.g., `+1 ••• ••• •• 71`) and HTTP error codes, never leaking raw digits, secret tokens, or sensitive queries.

### Workstream 6 — Remediation Integrity & Audit Trail
- **Audit Logging**: Implemented in both `routes.py::transition_action_endpoint` and `verifier.py::_update_remediation_action_record`. Every status transition inserts an immutable row into `action_audit_log`:
  ```sql
  INSERT INTO action_audit_log (id, action_id, identity_hmac, from_state, to_state, evidence_type, evidence_notes, created_at) ...
  ```
- **Evidence Verification Boundaries**:
  - `NO_LONGER_VISIBLE_AT_CHECKED_URL`: Requires affirmative HTTP 404/410 or live 200 with phone absence (`HTTP_ABSENCE_CHECK`).
  - `SOURCE_CONFIRMED_REMOVAL`: Strictly requires statutory deletion receipt or signed broker compliance notice (`STATUTORY_DELETION_RECEIPT`). URL disappearance is never promoted to source deletion.
  - `SEARCH_RESULT_DELISTED`: Search delisting is segregated under `SEARCH_INDEX_AUDIT`.
- **User Approval Boundary**: Backend rejects invalid transitions (e.g., `DISCOVERED` directly to `SUBMITTED` without user review and preparation) with HTTP 400.
- **Forensic Export**: `/api/privacy/export` includes the full `audit_trail` list alongside exposures, subscriptions, and spam incidents.

---

## 4. Quality Gate Results

### Test Results Summary

| Suite | Command | Total Tests | Passed | Failed | Duration |
|---|---|---|---|---|---|
| **SSRF Hardening** | `.venv\Scripts\pytest -v tests/test_ssrf.py` | 44 | 44 | 0 | 10.76s |
| **Discovery Benchmarks** | `.venv\Scripts\pytest -v tests/test_benchmark.py` | 4 | 4 | 0 | 4.45s |
| **API & Lifecycle Integration** | `.venv\Scripts\pytest -v tests/test_api.py tests/test_lifecycle.py` | 24 | 24 | 0 | 15.45s |
| **Playwright E2E Browser** | `.venv\Scripts\pytest -v tests/test_e2e_playwright.py` | 2 | 2 | 0 | 18.22s |
| **Complete Backend Test Suite** | `.venv\Scripts\pytest -v` | **132** | **132** | **0** | **92.13s** |
| **Frontend Linting** | `npm run lint` (oxlint) | 14 files | 14 | 0 | 0.82s |
| **Frontend Production Build** | `npm run build` (tsc + vite) | 1940 modules | 1940 | 0 | 25.28s |
| **Whitespace / Diff Check** | `git diff --check` | 18 files | 18 | 0 | 0.41s |

---

## 5. Reproduction Commands

To independently reproduce all validation results on a local machine:

```bash
# 1. Run full backend, integration, and SSRF security tests
.venv/Scripts/pytest -v

# 2. Run Playwright browser end-to-end tests
.venv/Scripts/pytest -v tests/test_e2e_playwright.py

# 3. Run the modular discovery benchmark suites via CLI
.venv/Scripts/python -m backend.app.cli.main benchmark

# 4. Verify frontend lint cleanliness (zero warnings)
cd frontend
npm run lint

# 5. Build production frontend bundle
npm run build
cd ..

# 6. Verify Git tree cleanliness and formatting
git diff --check
```

---

## 6. SSRF Residual Risks & Assumptions

1. **DNS Caching & TTL Assumptions**:
   - `SSRFSafeNetworkBackend` resolves DNS immediately before socket connection and pins the TCP connection to the first validated IP. If a host returns multiple A/AAAA records, it connects to the validated IP. If any returned record is in a private/loopback/cloud range, the entire host is rejected.
2. **Third-Party Libraries**:
   - Any future provider or parser that makes outbound network requests MUST use `safe_fetch_url` or `SSRFSafeTransport`. Direct use of `urllib.request`, bare `requests.get`, or default `httpx.AsyncClient` is strictly prohibited.
3. **Local SearXNG Trust**:
   - When a user configures a local SearXNG instance (`http://127.0.0.1:8888`), `validate_url_safe` would normally block loopback. A dedicated local SearXNG configuration hook must explicitly pin localhost only if explicitly enabled in user settings, without opening general outbound loopback.

---

## 7. Recommended Next Sprint

Now that the existing codebase is independently audited, secured, and measurable, the next engineering sprint can proceed safely to:

1. **Self-Hosted SearXNG Docker Compose Profile**:
   - Provide a zero-configuration local SearXNG container profile so users do not depend on rate-limited public instances.
2. **Additional Zero-Cost Public Data Adapters**:
   - Add open, auth-free public adapters (e.g. Internet Archive Wayback CDX API for historical exposures, GitHub public code search API).
3. **Automated Verification Scheduler (Local Daemon)**:
   - Implement optional background verification checks for pending removals on user-defined intervals (e.g., every 7 days) with strict rate-limiting.
4. **Encrypted Local Storage**:
   - Add optional SQLCipher or passphrase-derived envelope encryption for the local SQLite database at rest.
