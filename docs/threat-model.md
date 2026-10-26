# NumberShield — Threat Model & Security Architecture

This document presents the security evaluation and threat model for **NumberShield**, structured around the **STRIDE** methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege).

---

## 1. System Boundary and Assets

### Assets
1. **Target Phone Number**: The user's personal telephone number in normalized (E.164) and formatted variants.
2. **Exposure & Remediation Database**: Local SQLite database storing discovered URLs, evidence snippets, remediation statuses, and timestamps.
3. **User-Imported Data**: Local `.mbox` email archives and SMS backups containing private messages.
4. **Local Network & Environment**: The user's operating system, filesystem, and local loopback network.

### Trust Boundaries
- **Boundary 1 (User / Application)**: Interactive input via CLI or Web UI on `127.0.0.1`.
- **Boundary 2 (Application / Local Storage)**: SQLite file and local encryption keys on the host filesystem.
- **Boundary 3 (Application / External Web)**: Outbound HTTP requests to search engines and target web pages during verification.
- **Boundary 4 (External Content / HTML Parser)**: Untrusted HTML, headers, and metadata fetched from external third-party servers.

---

## 2. STRIDE Analysis & Mitigations

### 2.1 Spoofing (Identity & Ownership)
- **Threat**: A user enters someone else's phone number to perform unauthorized surveillance or submit fraudulent opt-out requests.
- **Impact**: Harassment, unauthorized profile modifications, or privacy violations.
- **Mitigation**:
  1. **Local-First Design**: NumberShield is strictly a personal desktop tool running on `127.0.0.1`. It does not offer a multi-tenant public web service where arbitrary callers can scan third parties.
  2. **Zero Automated Account Alteration**: NumberShield **never** submits requests automatically. Every remediation action requires conscious, manual user execution through official channels (which typically require SMS or email verification belonging to the actual number owner).
  3. **Responsible Use Disclosure**: Mandatory legal acknowledgment banner displayed on first run.

### 2.2 Tampering (Data Modification)
- **Threat**: Malicious websites manipulate HTML structure to inject false matches, deceptive opt-out URLs, or prompt-injection text designed to manipulate AI agents or parsers.
- **Impact**: False remediation records or misdirected user navigation.
- **Mitigation**:
  1. **Strict Context Matching**: Digit sequences are only classified as matches if they strictly adhere to national numbering plan lengths and contextual proximity.
  2. **Source Registry Immutability**: All official opt-out URLs are hardcoded in a vetted, version-controlled registry (`remediation/registry.py`) with strict schema validation—not dynamically scraped from untrusted pages.

### 2.3 Repudiation (Action Verifiability)
- **Threat**: Users or data brokers dispute whether a removal request was submitted or when an exposure was discovered.
- **Impact**: Inability to hold data brokers accountable under statutory timelines (e.g., CCPA 45-day window, GDPR 30-day window).
- **Mitigation**:
  1. **Immutable Action Log**: Every lifecycle state change (`SUBMITTED`, `ACKNOWLEDGED`, `VERIFIED_REMOVED`) records an ISO 8601 UTC timestamp, confirmation reference ID, and HTTP status code.
  2. **Cryptographic Proof of Page State**: Verification checks capture HTTP status codes (200, 404, 410) and SHA-256 hashes of the target page HTML.

### 2.4 Information Disclosure (Privacy Leaks)
- **Threat A**: Outbound HTTP requests leak the user's phone number to untrusted third parties.
  - *Mitigation*: External discovery is restricted to meta-search queries. Verification rescans fetch the page URL only (standard HTTP GET without query parameters containing numbers). Direct browser dorks run inside the user's browser, preventing app-level telemetry.
- **Threat B: Server-Side Request Forgery (SSRF)**:
  - *Attack*: An attacker enters a malicious URL (e.g., `http://169.254.169.254/latest/meta-data/` or `http://127.0.0.1:8080/admin`) to probe the user's internal network or cloud metadata.
  - *Mitigation*: Our `SafeHTTPFetcher` resolves target hostnames before making requests and rejects:
    - Loopback addresses (`127.0.0.0/8`, `::1`).
    - Private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
    - Link-local addresses (`169.254.0.0/16`, `fe80::/10`).
    - Multicast and reserved ranges.
    - Non-HTTP/HTTPS schemes (e.g., `file://`, `gopher://`, `ftp://`).
    - Malicious HTTP redirects targeting internal IPs (each redirect hop is re-validated).
- **Threat C: Log & Console Leakage**:
  - *Attack*: Phone numbers appear in console stdout, web logs, or stack traces.
  - *Mitigation*: A central `PhoneNumberRedactor` filter intercepts all log records and scrubs any recognized phone number or variant before writing to output.

### 2.5 Denial of Service (Resource Exhaustion)
- **Threat A: ReDoS (Regular Expression Denial of Service)**:
  - *Attack*: Pathological HTML text designed to trigger catastrophic backtracking on phone number regexes.
  - *Mitigation*: All regexes use atomic non-overlapping groups with bounded repetition limits (`{7,15}`). `phonenumbers` uses compiled state machines.
- **Threat B: HTTP Decompression Bombs & Giant Responses**:
  - *Attack*: Scanning a URL that returns gigabytes of streaming data.
  - *Mitigation*: Hard limits on response size (maximum 5 MB per page) and strict connection timeouts (10 seconds total, 5 seconds connect).

### 2.6 Elevation of Privilege (Code Execution)
- **Threat**: Malicious HTML containing `<script>` tags or XSS payloads executing in the dashboard UI.
- **Impact**: Unauthorized execution of browser commands.
- **Mitigation**:
  1. **Strict HTML Stripping**: Discovered evidence snippets are sanitized via BeautifulSoup and stripped of all HTML tags, attributes, and scripts before storage.
  2. **React Context Escaping**: The React frontend renders evidence exclusively via safe text nodes (`{snippet}`), preventing raw DOM injection (`dangerouslySetInnerHTML` is strictly prohibited).
  3. **Localhost Binding**: FastAPI server binds strictly to `127.0.0.1`, refusing external network connections.
