# NumberShield — System Architecture

## 1. System Overview

**NumberShield** is structured as three loosely coupled, deterministic engines operating over a shared local-first database and coordinated by a lightweight FastAPI backend and Typer CLI:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          NumberShield System                           │
└────────────────────────────────────────────────────────────────────────┘
          │                                 │
          ▼                                 ▼
┌──────────────────┐               ┌──────────────────┐
│  CLI (Typer)     │               │  Web UI (React)  │
└──────────────────┘               └──────────────────┘
          │                                 │
          └─────────────────┬───────────────┘
                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      FastAPI Application Gateway                       │
│    • Localhost-only (127.0.0.1) • Log Redactor • SSRF Protection       │
└────────────────────────────────────────────────────────────────────────┘
        │                         │                         │
        ▼                         ▼                         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ Discovery Engine │     │Remediation Engine│     │Prevention Engine │
│ • Normalizer     │     │ • Source Registry│     │ • Incident Log   │
│ • Matcher        │     │ • State Machine  │     │ • Campaign Group │
│ • Search Prov.   │     │ • Legal Templates│     │ • DND Guides     │
│ • Local Parsers  │     │ • Search De-index│     │ • Rescan Verify  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
        │                         │                         │
        └─────────────────┬───────┴─────────────────────────┘
                          ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Local Storage & Crypto Boundary                      │
│       • SQLite Database (`numbershield.db`)                            │
│       • Keyed HMAC-SHA256 (`.numbershield_key`)                        │
│       • Zero-Trace Cryptographic Purge (`/purge`)                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The Three Core Engines

### 2.1 The Discovery Engine (`backend/app/engines/discovery`)

The Discovery Engine identifies where a user's phone number appears across public websites, code repositories, pastes, and user-authorized local files.

1. **Country-Aware Phone Normalizer (`normalizer.py`)**:
   - Parses the input string using Google's `phonenumbers` library.
   - Extracts metadata: Country code, national significant number, geographic region/subdivision, carrier block allocation, and telephony line type (Mobile, Fixed Line, VoIP, Toll Free).
   - Generates standardized search query variants:
     - `e164`: `+14155552671`
     - `international`: `+1 415-555-2671`
     - `national`: `(415) 555-2671`
     - `dashed`: `415-555-2671`
     - `dotted`: `415.555.2671`
     - `spaced`: `415 555 2671`
     - `digits_only`: `4155552671`
     - `rfc3966`: `tel:+1-415-555-2671`

2. **Context-Aware Matcher (`matcher.py`)**:
   - Evaluates potential candidate matches against 4 strict confidence tiers:
     - `EXACT` (1.0): Full national or international sequence matching target with exact country prefix or local area format.
     - `PROBABLE` (0.8): Local format matching in a document with country-consistent currency, address, or language context.
     - `WEAK` (0.4): Loose digits matching length but lacking area or country confirmation.
     - `FALSE_POSITIVE` (0.0): Numeric sequences that represent dates (e.g., `2026-10-24`), UUIDs, ISBNs, part numbers, or tracking codes.
   - Extracts surrounding context snippets (±120 characters) and strips all HTML tags.

3. **Pluggable Search Providers (`providers/`)**:
   - Extensible `SearchProvider` abstract base class.
   - `SearXNGProvider`: Queries public or private SearXNG meta-search engines with JSON formatting.
   - `DuckDuckGoProvider`: Queries DuckDuckGo HTML/Lite with polite backoff.
   - `ManualDorksProvider`: Generates pre-computed, URL-encoded search links for Google, Bing, Brave, Yahoo, Yandex, Pastebin, GitHub, and major directory engines for 1-click execution in the user's browser.

4. **Local File Analyzers (`local_parsers/`)**:
   - `MBOXParser`: Reads user-exported email archives. Detects commercial email senders, `List-Unsubscribe` headers, phone signatures, and SMS notification emails.
   - `SMSBackupParser`: Reads Android/iOS SMS backups (XML/JSON/CSV). Detects commercial shortcodes (5-6 digits), marketing SMS blasts, and opt-out keywords ("STOP", "END", "CANCEL").

---

### 2.2 The Remediation Engine (`backend/app/engines/remediation`)

The Remediation Engine provides actionable, legally grounded, and source-specific pathways to remove discovered exposures.

1. **Source Registry (`registry.py`)**:
   - Maintained registry of 25+ data brokers, people-search directories, platforms, search engines, and regulators:
     - FastPeopleSearch, TruePeopleSearch, Whitepages, Radaris, Spokeo, Nuwber, CyberBackgroundChecks, That'sThem, AnyWho, BeenVerified, Intelius, USPhoneBook, PeekYou.
     - Google Outdated Content & PII Removal.
     - Bing Content Removal.
     - National DND Registries (US, UK, IN, CA, AU).
   - Maps each domain to official opt-out URLs, suppression requirements, turnaround estimates, and verification requirements.

2. **Truthful Lifecycle State Machine (`lifecycle.py`)**:
   Enforces valid state transitions:
   - `DISCOVERED` -> `VERIFIED` -> `ACTION_AVAILABLE` -> `SUBMITTED` -> `ACKNOWLEDGED` -> `VERIFIED_REMOVED`
   - Permitted side transitions to `REJECTED` (false positive), `MANUAL_ACTION_REQUIRED`, `FAILED`, `PENDING`.
   - Rejects unevidenced transitions (e.g., cannot mark `VERIFIED_REMOVED` without an automated verification scan or user verification proof).

3. **Privacy Rights & Legal Template Generator (`templates.py`)**:
   Generates customized, privacy-masked formal notices:
   - CCPA / CPRA Request to Delete and Opt-Out of Sale (California).
   - GDPR Article 17 (Right to Erasure) & Article 21 (Right to Object) (EU/UK).
   - US FTC / FCC Do Not Call Violation Complaint.
   - UK TPS / ICO Nuisance Call Report.
   - India TRAI 1909 UCC Complaint Format.
   - Universal Merchant Opt-Out & Cease Processing Notice.

4. **Search Engine De-Indexing Guides (`search_removal.py`)**:
   - Workflow guides for Google Search PII Removal and Outdated Content Tool.
   - Bing Content Removal instructions.

---

### 2.3 The Prevention and Verification Engine (`backend/app/engines/prevention`)

The Prevention Engine minimizes future unwanted contact and measures real-world progress.

1. **Spam Incident Logger (`incident_tracker.py`)**:
   - Records spam calls and texts with timestamp, sender number/shortcode, call category (Robocall, Live agent, SMS, WhatsApp), caller ID spoof suspicion, and sales campaign pitch.

2. **Campaign Analyzer (`campaign_analyzer.py`)**:
   - Groups incidents by area code, sender patterns, and common keywords to identify repeat marketing syndicates.

3. **Exposure Rescan & Verifier (`verifier.py`)**:
   - Safely rescans discovered exposure URLs.
   - Evaluates whether the phone number is still present in the page text.
   - Detects HTTP 404 (Not Found), 410 (Gone), or content suppression, automatically transitioning remediation actions to `VERIFIED_REMOVED` when verified.

4. **Before-and-After Trend Metrics (`metrics.py`)**:
   - Computes unwanted contact frequency over time, remediation resolution rate, and average time-to-remediate.

---

## 3. Database Schema

NumberShield uses SQLite (`numbershield.db`) with tables:
- `identities`: Keyed HMAC ID, masked phone display, country code, carrier name, line type, created timestamp.
- `exposures`: ID, identity_hmac, source_id, url, title, match_type, confidence, snippet, discovered_at, last_checked_at.
- `remediation_actions`: ID, exposure_id, identity_hmac, source_id, status, official_url, submission_ref, notes, submitted_at, verified_at, updated_at.
- `subscriptions`: ID, identity_hmac, sender_name, sender_contact, channel (EMAIL/SMS), unsubscribe_method, unsubscribe_target, status, created_at.
- `spam_incidents`: ID, identity_hmac, sender_number, channel, category, spoof_suspected, campaign_summary, reported_at.
