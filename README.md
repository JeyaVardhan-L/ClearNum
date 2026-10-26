# NumberShield 🛡️

**A Free, Open-Source, Local-First Phone-Number Privacy & Spam Reduction Platform.**

NumberShield helps individuals discover where their phone number is exposed online, audit marketing subscriptions from local records, generate legally grounded opt-out notices (CCPA/CPRA, GDPR, TCPA, TRAI 1909), and track verified removals through a truthful lifecycle state machine—with **zero mandatory cost, zero telemetry, and zero cloud lock-in**.

---

## ⚡ Key Highlights & Guarantees

- **100% Free & Open-Source**: Zero paid APIs, zero subscriptions, zero paid LLMs, zero cloud dependencies.
- **Strictly Local-First**: Runs entirely on `127.0.0.1`. Your raw phone number never leaves your computer.
- **Cryptographic Privacy Isolation**: Stored phone numbers are indexed exclusively via 256-bit keyed HMAC-SHA256 (`.numbershield_key`) to prevent offline rainbow-table recovery.
- **Zero-Trace Cryptographic Purge**: A single command or click securely overwrites database records and wipes runtime memory keys.
- **Truthful Lifecycle State Machine**: Enforces verified state transitions (`DISCOVERED` → `VERIFIED` → `ACTION_AVAILABLE` → `SUBMITTED` → `ACKNOWLEDGED` → `VERIFIED_REMOVED`). No fake instant deletion promises.
- **SSRF Hardened**: Outbound verification requests strictly block loopback, RFC 1918 private subnets, cloud metadata (`169.254.169.254`), and non-HTTP protocols.
- **Universal Log Redactor**: Raw phone digits are scrubbed from all terminal outputs, system logs, and exception tracebacks in real time.

---

## 🏗️ Architecture Overview

```
                                 +----------------------------------------------------+
                                 |         Local Web UI (React + Vite + Tailwind)     |
                                 |         Terminal CLI (Typer + Rich Formatting)     |
                                 +-------------------------+--------------------------+
                                                           |
                                                REST API / Localhost Only
                                                           |
+----------------------------------------------------------v----------------------------------------------------------+
|                                             NUMBERSHIELD CORE ENGINE                                                |
|                                                                                                                     |
|  +---------------------------+   +---------------------------------------+   +-----------------------------------+  |
|  |     DISCOVERY ENGINE      |   |          REMEDIATION ENGINE           |   |       PREVENTION & METRICS        |  |
|  +---------------------------+   +---------------------------------------+   +-----------------------------------+  |
|  | * libphonenumber Parser   |   | * 25+ Curated Data Broker Directory   |   | * Spam Incident & Pattern Logger  |  |
|  | * 10+ Country Normalizer  |   | * Statutory Notice Generators:        |   | * Syndicate Pattern Clustering    |  |
|  | * Permutation Generator   |   |   - CCPA/CPRA Deletion                |   | * Live SSRF-Safe URL Verifier     |  |
|  | * False Positive Rejection|   |   - GDPR Art. 17 / 21 Erasure         |   | * Truthful Before-and-After       |  |
|  | * SearXNG & DuckDuckGo    |   |   - TCPA / Merchant Revocation        |   |   Frequency & Impact Metrics      |  |
|  | * 1-Click Manual Dorks    |   |   - TRAI 1909 Commercial Notice       |   |                                   |  |
|  | * Local MBOX Email Parser |   | * Search Engine Delisting Guides      |   |                                   |  |
|  | * Local SMS Backup Parser |   | * Truthful State Transition Engine    |   |                                   |  |
|  +-------------+-------------+   +-------------------+-------------------+   +-----------------+-----------------+  |
|                |                                     |                                         |                    |
+----------------v-------------------------------------v-----------------------------------------v--------------------+
                                                       |
                                      +----------------v----------------+
                                      |    LOCAL STORAGE & SECURITY     |
                                      +---------------------------------+
                                      | * SQLite (WAL Mode, Local Only) |
                                      | * 256-bit Keyed HMAC Isolation  |
                                      | * Zero-Trace Memory/DB Purge    |
                                      +---------------------------------+
```

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** (tested up to Python 3.14)
- **Node.js 18+** & **npm** (for building the frontend)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/numbershield.git
   cd numbershield
   ```

2. **Set up Python Virtual Environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux / macOS:
   source .venv/bin/activate

   pip install -e .
   ```

3. **Build the Frontend:**
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```
   *The FastAPI backend automatically serves the compiled static bundle from `frontend/dist` at the root URL.*

4. **Launch NumberShield:**
   ```bash
   numbershield serve
   ```
   Open your browser at **`http://127.0.0.1:8765`**.

---

## 💻 Command Line Interface (CLI)

NumberShield includes a full-featured terminal CLI powered by Typer and Rich:

```bash
# Display help and command listing
numbershield --help

# Parse and normalize a phone number across international formats
numbershield parse "+14155552671"

# Generate search engine dorks for manual zero-cost OSINT auditing
numbershield dorks "+14155552671"

# List curated data broker directory and opt-out methods
numbershield sources

# Generate legally grounded statutory opt-out templates
numbershield template ccpa --phone "+14155552671" --name "Jane Doe" --broker "FastPeopleSearch"
numbershield template gdpr --phone "+442079460991" --name "John Smith"
numbershield template tcpa --phone "+14155552671" --name "Jane Doe" --merchant "Acme Telemarketing"
numbershield template trai --phone "+919876543210" --name "Rahul Sharma"

# View National Do Not Call (DND) registration instructions
numbershield dnd us
numbershield dnd in
numbershield dnd uk

# Verify if a phone number remains exposed on a public URL (SSRF protected)
numbershield verify "https://pastebin.com/raw/example" "+14155552671"

# Load realistic demonstration data to evaluate workflows offline
numbershield demo

# Securely wipe all stored records and reset HMAC keys
numbershield purge

# Start the local web dashboard
numbershield serve --host 127.0.0.1 --port 8765
```

---

## 🖥️ Web Dashboard Walkthrough

### 1. Scan Console (`/`)
- **Interactive Telephony Normalizer**: Real-time validation across 10+ countries (US, UK, IN, DE, FR, JP, AU, CA, BR, SG), international E.164 formatting, and search variant generation.
- **Provider Selector**: Configurable local SearXNG instance URL, HTML DuckDuckGo fallback, or direct URL ingestion.
- **1-Click Manual Search Dorks**: Instant modal with pre-formatted search queries targeting data brokers, public paste sites, PDFs, contact pages, and leaked spreadsheets.

### 2. Discovered Exposures
- **Dense Audit Table**: View detected URLs, discovery source, match confidence score (`EXACT`, `PROBABLE`, `WEAK`), and lifecycle status.
- **Live SSRF-Safe Re-Verification**: Test whether a public URL still leaks the phone number before claiming remediation.
- **State Transition Controller**: Move items strictly through legitimate lifecycle steps.

### 3. Remediation Hub
- **25+ Curated Data Brokers**: Directory of major people-search brokers (FastPeopleSearch, TruePeopleSearch, Spokeo, Whitepages, Radaris, LexisNexis, etc.) with verified opt-out URLs, required verification info, and expected turnaround times.
- **Legal Notice Generator**: Generate formal statutory letters citing CCPA/CPRA Cal. Civ. Code § 1798.105, GDPR Art. 17/21, TCPA 47 U.S.C. § 227, or TRAI Telecom Commercial Communications Regulations 1909.
- **Export & Copy**: Instant copy or markdown download of customized legal letters.
- **Search Delisting**: Step-by-step guides for Google PII Removal and Microsoft Bing Delisting.

### 4. Prevention & DND Hub
- **Spam Incident Tracker**: Log unwanted marketing calls/SMS with sender ID, date, call type, and opt-out status.
- **Syndicate Pattern Clustering**: Group spam incidents by recurring patterns and area codes.
- **National DND Guides**: Actionable registration steps for US FTC (`donotcall.gov`), UK TPS (`tpsonline.org.uk`), India TRAI (`1909`), Canada DNCL, and Australia Do Not Call Register.
- **Carrier 7726 Guide**: How to report spam SMS to mobile networks using the global `7726` shortcode.

### 5. Verification & Audit Trail
- **Local MBOX & SMS Parsers**: Parse exported Gmail/Thunderbird `.mbox` archives or Android SMS XML backups completely offline to extract marketing subscription senders and opt-out links.
- **Truthful Before-and-After Metrics**: Real-time charts of total exposures, verified removals, spam call frequencies, and remediation turnaround.
- **Forensic Audit Log Export**: Download signed JSON audit reports of all actions for dispute resolution.
- **Cryptographic Purge**: Instant zero-trace erasure of all records.

---

## 🔒 Security & Privacy Engineering

| Component | Protection Mechanism |
| :--- | :--- |
| **Phone Number Storage** | Indexed exclusively with **256-bit keyed HMAC-SHA256**. Key stored in `.numbershield_key` with strict filesystem permissions (`0600`). Prevents pre-computed rainbow table lookups if database is accessed. |
| **Outbound Requests (SSRF)** | Enforces strict network boundaries. Outbound HTTP requests automatically resolve hostnames and block loopback (`127.0.0.0/8`), private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local metadata (`169.254.169.254`), and non-HTTP protocols. |
| **Log Sanitization** | `backend/app/core/redactor.py` filters all log output and console streams using international regex pattern matching, masking digits to `+1 ••• ••• •• 71`. |
| **Data Purge** | Cryptographic purge drops and vacuums database tables, unlink `.numbershield_key`, and overwrites memory buffers with zeros. |
| **Zero Telemetry** | No Google Analytics, no error reporting pings, no cloud telemetry, no third-party CDN scripts. |

---

## 🧪 Testing & Quality Assurance

NumberShield includes a comprehensive automated test suite with **61 passing tests**:

- **Unit Tests**: Normalizer, Phone Permutations, Fuzzy Matcher, False Positive Date/UUID Rejection, SSRF Network Filter, Keyed HMAC, Redactor.
- **Local Parser Tests**: MBOX parsing, Android SMS XML parsing.
- **Lifecycle Tests**: Valid and invalid state transitions, rejection handling, premature removal prevention.
- **Integration Tests**: FastAPI REST endpoints, schema validation, fixture generation, purge flow.
- **End-to-End Browser Tests**: Playwright automated testing across desktop and mobile viewports (`390x844`).

To run the complete test suite:
```bash
pytest -v
```

---

## ⚠️ Limitations & Legal Disclaimer

1. **Non-Legal Advice**: NumberShield produces legally grounded statutory notice templates based on public statutes (CCPA, GDPR, TCPA, TRAI). It does not provide formal legal representation or guarantee compliance by non-compliant overseas bad actors.
2. **Opt-Out Reality**: Legitimate domestic data brokers honor statutory opt-outs within 48 to 72 hours. Offshore illegal spam syndicates ignore Do Not Call registries and must be mitigated using telecom-level call blocking and carrier 7726 reporting.
3. **Automated CAPTCHA / Bot Restrictions**: NumberShield deliberately does **not** bypass CAPTCHAs or breach third-party Terms of Service. Where data brokers require human CAPTCHA verification, NumberShield provides direct pre-filled opt-out links and guidance.

---

## 📄 License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
