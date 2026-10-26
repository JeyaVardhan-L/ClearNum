# NumberShield — Research Decisions and Architecture Trade-offs

This document details the architectural decisions, trade-offs, and design rationale behind **NumberShield**, explaining why specific approaches were selected and why alternatives were rejected.

---

## 1. Zero-Cost Architecture vs. Paid Convenience

### The Temptation
Many commercial privacy and OSINT platforms rely on paid APIs:
- Data broker removal services (DeleteMe, Incogni, Kanary) charge $10-$15/month to submit repetitive opt-out forms via automated scripts and legal power-of-attorney.
- OSINT scanners (SpiderFoot HX, IntelX, Pipl) require commercial keys costing hundreds of dollars per month.
- Phone validation tools (Numverify, Telesign, Twilio) charge per lookup.

### Our Decision
**NumberShield commits to 100% zero-cost operation.**
1. **Local-first telephony parsing**: We use Google's `libphonenumber` (via the Python `phonenumbers` port), which bundles complete numbering plans, carrier prefix tables, and geographical mappings locally. It costs zero, performs lookups in microseconds, and requires zero network requests.
2. **Decoupled Search Provider architecture**: Rather than requiring an expensive Google Custom Search API key ($5 per 1,000 queries) or paid scraping proxy (ScraperAPI/BrightData), NumberShield combines:
   - Pluggable open meta-search (SearXNG).
   - Polite web search fallback (DuckDuckGo Lite).
   - One-click direct browser dork workflows (Google, Bing, Brave, Yahoo, Yandex, GitHub, Pastebin) executed directly by the user's browser, bypassing CAPTCHAs naturally without paid solving services.
3. **Local-first SQLite storage**: No cloud database accounts, AWS RDS, or Firebase subscriptions required. Everything runs locally on `127.0.0.1`.

---

## 2. Anti-Bot Defenses and Ethical Boundaries

### The Problem
Major people-search directories (Whitepages, FastPeopleSearch, TruePeopleSearch, Radaris, Nuwber) implement aggressive Cloudflare Turnstile, Datadome, and Akamai bot-mitigation systems.

### Evaluated Alternatives
- *Option A: Reverse-engineer APIs or use headless browser evasion (puppeteer-stealth)*.
  - **Verdict: Rejected.** Fragile, easily broken on site updates, high risk of IP bans, and violates website Terms of Service.
- *Option B: Integrate third-party CAPTCHA-solving services (2Captcha, Anti-Captcha)*.
  - **Verdict: Rejected.** Violates the zero-cost constraint and introduces external account dependencies and ethical issues.
- *Option C: Search Index Discovery + Verified Remediation Registry*.
  - **Verdict: Selected.**
    1. Search engines have already indexed public directory profile pages where phone numbers appear. Querying search engines surfaces the exact profile URL where the number is exposed.
    2. Instead of scraping, NumberShield maintains a verified registry of **Official Opt-Out URLs**, suppression forms, and email channels.
    3. The application guides the user step-by-step through the broker's official opt-out flow, pre-populating required fields to the clipboard, providing legal removal templates, and logging submission timestamps.

---

## 3. Local-First Email & SMS Analysis vs. Cloud Connectors

### The Problem
Unwanted marketing calls and text spam often originate from commercial subscriptions, e-commerce signups, and marketing lists where the user previously entered their phone number.

### Evaluated Alternatives
- *Option A: Build Google Workspace / Microsoft 365 OAuth cloud apps*.
  - **Verdict: Rejected.** Requires cloud hosting, OAuth verification by Google/Microsoft (costly review process), and grants broad email access across the internet.
- *Option B: Local file import of user-exported MBOX archives and SMS backups*.
  - **Verdict: Selected.**
    1. Users export their emails (`.mbox` from Gmail Google Takeout, Thunderbird, Apple Mail) or SMS backup (`.xml`/`.json`/`.csv` from Android SMS Backup & Restore).
    2. NumberShield parses these files entirely in local memory on the user's machine.
    3. The engine parses `List-Unsubscribe` headers, opt-out keywords ("Reply STOP", "Unsubscribe"), and shortcodes (`5-6` digits).
    4. **Zero network egress**: No email or message content leaves the device.

---

## 4. Truthful Remediation Lifecycle

### The Problem
Commercial removal services often present deceptive progress bars, claiming "100% of your data has been deleted from the internet!" within seconds of signup. In reality, data brokers take 24-72 hours to process requests, frequently require email or SMS verification links to be clicked, and may re-scrape public voter/property records months later.

### Our Lifecycle State Machine
NumberShield enforces an honest, evidence-based lifecycle:

```
[Discovered]
     │
     ▼ (User reviews context and confirms match)
 [Verified]
     │
     ▼ (Official opt-out procedure identified)
[Action Available]
     │
     ▼ (User submits official request & enters confirmation ref)
 [Submitted]
     │
     ▼ (Broker emails acknowledgment or ticket confirmation)
[Acknowledged]
     │
     ▼ (Rescan engine verifies page returns 404 or content cleared)
[Verified Removed]
```

Side states:
- `Rejected`: Marked as false-positive match by user.
- `Manual Action Required`: Requires physical phone call, mail-in request, or photo ID suppression.
- `Pending`: Awaiting standard processing window (e.g., 48 hours).
- `Failed`: Broker rejected request or form timed out.
- `Unable to Verify`: Page blocked or site returned ambiguous response.

---

## 5. Storage Security and Phone Number Redaction

### The Threat
If NumberShield stores phone numbers in plaintext on disk, a local malware infection or unauthorized computer user could extract the user's phone number and exposure history. Furthermore, debug logs and error messages frequently leak sensitive parameters.

### Our Security & Redaction Model
1. **Keyed HMAC for Lookup Indexes**:
   - Rather than storing phone numbers as raw database primary keys, we compute `HMAC-SHA256(phone_e164, local_secret_key)`.
   - A standard hash (like unsalted SHA-256) is vulnerable to offline rainbow table enumeration (there are only ~10 billion valid global phone numbers). A locally generated 256-bit HMAC key stored in `.numbershield_key` prevents offline enumeration.
2. **Display Masking**:
   - All UI elements and logs redact phone numbers by default: `+1 (415) •••-••71`.
   - Full unmasked display requires deliberate user interaction (click-to-reveal).
3. **Log Sanitization Filter**:
   - A custom logging filter intercepts all logging records and applies regular expression redaction for all E.164 and localized telephone formats before writing to stdout or disk.
4. **Instant Cryptographic Purge (`/purge`)**:
   - A single command or button deletes all database tables, exposure records, logs, and resets the encryption key, ensuring zero residual footprint.

---

## 6. Source Expansion Research & Adapter Selection

In expanding automated discovery beyond generic web search, candidate public platforms were evaluated for incremental discovery value, authorized API access, zero mandatory cost, and terms of service compliance:

1. **Wikipedia / Wikimedia Document Search API (`WikimediaProvider`)**:
   - *Rationale for selection*: Wikimedia documents, user talk pages, project revisions, and event registration logs frequently preserve accidental PII disclosures. MediaWiki provides an official, free, stable REST/Action API (`en.wikipedia.org/w/api.php`) with no authentication requirements and a generous 200 req/sec limit under its documented User-Agent policy.
   - *Implementation*: NumberShield includes a custom identifying User-Agent (`NumberShield/1.0`), extracts high-provenance article titles and cleaned snippets, and formats direct canonical URLs.

2. **Hacker News Algolia Search API (`HackerNewsProvider`)**:
   - *Rationale for selection*: Technical forums, "Ask HN: Who is hiring? / Who wants to be hired?" threads, and startup launch discussions frequently contain public comments with personal contact details and support numbers. Algolia provides the official public search engine for Hacker News with an open JSON API (`hn.algolia.com/api/v1/search`), 10,000 requests/hour allowance, and zero authentication.
   - *Implementation*: Queries comment and story text for exact phone permutations, parses item IDs, and links directly to official Hacker News discussion threads.

3. **GitHub Code Search API (Automated API Rejected; Direct Browser Dorking Selected)**:
   - *Evaluation*: GitHub's public Code Search API (`api.github.com/search/code`) strictly requires authenticated Personal Access Tokens (returning HTTP 401 for anonymous calls) and imposes tight rate limits (10-30 req/min). Forcing users to create GitHub developer tokens contradicts NumberShield's zero-friction, zero-account philosophy.
   - *Solution*: Automated unauthenticated API was rejected. Instead, targeted GitHub Code Search dorks (`site:github.com` or `https://github.com/search?type=code&q=...`) are provided in the 1-click Manual Dork Generator, allowing the user to execute deep code searches within their existing browser session.

4. **Pastebin Scraping (Rejected in favor of Search Index Dorking)**:
   - *Evaluation*: Pastebin implements Cloudflare protection on its public interface and charges for its scraping API ($50+ lifetime/commercial). Direct scraping violates ToS and risks automated IP bans.
   - *Solution*: Discovery of leaked pastes is performed via indexed search engine dorks (`site:pastebin.com ...`), achieving paste discovery at zero cost without bot evasion.
