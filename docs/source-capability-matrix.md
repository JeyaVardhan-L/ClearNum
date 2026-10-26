# NumberShield — Source Capability Matrix

This document provides a rigorous, verified capability evaluation of candidate tools, search engines, OSINT utilities, breach checkers, and public directories considered for **NumberShield**.

Every candidate is evaluated against seven mandatory criteria:
1. **Actual Discovery Scope**: What data it physically discovers.
2. **Cost & Commercial Terms**: Whether it operates genuinely without payment or hidden paywalls.
3. **Registration & Auth**: Whether API keys, account creation, or phone verification are required.
4. **Quotas & Rate Limits**: Known limits, burst caps, and anti-scraping defenses.
5. **License & Redistribution**: Legality of redistribution and usage within an open-source tool.
6. **Data Egress & Privacy Impact**: What user information leaves the local device.
7. **Unique Value vs. Duplication**: Whether it contributes new coverage or duplicates existing sources.

---

## 1. Candidate Source Evaluation Table

| Source / Tool | Category | Zero Cost? | Auth Required? | Discovery Scope | Egress Data | Status in NumberShield |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **libphonenumber (`phonenumbers`)** | Offline Telephony | Yes (100% Free) | None | Country, carrier metadata, line type, format variants | None (100% Local) | **Core Engine** (Mandatory) |
| **SearXNG Instances** | Meta-Search | Yes | None (on open instances) | Aggregated web search results (Google, Bing, DDG, Mojeek) | Search query only | **Implemented Provider** |
| **DuckDuckGo HTML / Lite** | Web Search | Yes | None | Indexed public web mentions, forums, pastes, listings | Search query only | **Implemented Provider** (with backoff) |
| **Direct Browser Dorks** | Search Workflows | Yes | None | Google, Bing, Brave, Yahoo, Yandex, GitHub, Pastebin | Handled in user browser | **Implemented Workflow** (1-click) |
| **Local MBOX Parser** | User-Authorized Email | Yes | None | Unsubscribe headers, marketing lists, signatures | None (100% Local) | **Implemented Feature** |
| **Local SMS Backup Parser** | User-Authorized SMS | Yes | None | Commercial shortcodes, spam senders, opt-out words | None (100% Local) | **Implemented Feature** |
| **Public Directory Opt-Outs** | Remediation Registry | Yes | None (manual) | 25+ data brokers (Whitepages, TruePeopleSearch, Radaris, etc.) | Target profile URL | **Implemented Remediation Hub** |
| **Google/Bing Removal Tools** | Outdated Content/PII | Yes | Free Google/MS Account | De-indexing cached numbers and PII from search indexes | Exposure URL & search snippet | **Implemented Assisted Flow** |
| **National Telecom DND** | Regulatory Portals | Yes | None/SMS Auth | Official spam suppression (US, UK, IN, CA, AU) | Phone number (to regulator) | **Implemented Action Hub** |
| **PhoneInfoga** | OSINT Scanner | Partially Free | Optional APIs (Numverify, OVH) | Dork URLs, carrier type, telecom footprint | Queries to external endpoints | **Patterns Adopted Locally** |
| **HaveIBeenPwned (HIBP)** | Breach Intelligence | No (for arbitrary phone queries) | Paid API key for automated check | Breaches containing account info (Phone only in FB 2021) | PII to external API | **Disclosed / Manual Guidance** |
| **SpiderFoot** | OSINT Framework | Free framework, Paid modules | API keys for 80% of modules | General entity OSINT (massive dependency overhead) | Broad queries to external services | **Rejected** (Overhead & Paid APIs) |
| **Scraping Data Brokers Directly** | Unofficial Scrapers | No (Blocked by Cloudflare) | CAPTCHA bypass required | Profile details on people search sites | Scraping traffic flagged as bot | **Rejected** (ToS violation & fragility) |

---

## 2. Detailed Candidate Profiles

### A. Core Telephony: `libphonenumber` / `phonenumbers`
- **What it discovers**: Offline parsing of E.164 and national numbering plans, country codes, geographic region, line type (MOBILE, FIXED_LINE, VOIP, TOLL_FREE, PREMIUM_RATE, SHARED_COST), and original carrier allocation blocks.
- **Cost**: 100% free, open-source (Apache 2.0).
- **Credentials**: None.
- **Quotas**: Unlimited local processing throughput.
- **Data Egress**: **Zero**. Executes entirely in local memory.
- **Verdict**: **Adopted as primary parser**.

### B. Meta-Search: SearXNG
- **What it discovers**: Aggregated search results from dozens of engines without tracking or user profiling.
- **Cost**: 100% free (open-source AGPL-3.0, self-hostable or usable via public instances).
- **Credentials**: None for standard public JSON endpoints (`/search?q=...&format=json`).
- **Quotas**: Public instances rate limit rapid bursts (typically 1 req/sec). NumberShield provides configurable instance URLs and graceful timeout handling.
- **Data Egress**: Search query containing the formatted number string.
- **Verdict**: **Adopted as default extensible search provider**.

### C. Web Search: DuckDuckGo HTML / Lite
- **What it discovers**: Search results from DuckDuckGo's non-JavaScript endpoint.
- **Cost**: Free.
- **Credentials**: None.
- **Quotas**: Susceptible to HTTP 202/403 bot challenges if queried rapidly. Requires courteous delays (1.5s+), browser-like User-Agents, and automated fallback to manual dork links.
- **Data Egress**: Search query string.
- **Verdict**: **Adopted with exponential backoff and manual fallback**.

### D. Direct Browser Dorking Engine
- **What it discovers**: Complete query coverage across Google, Bing, Brave, Yahoo, Yandex, GitHub, Pastebin, and specialized people search engines.
- **Cost**: 100% free.
- **Credentials**: None needed by the app. Uses user's existing browser session.
- **Quotas**: Immune to automated bot blocks because the user executes the query in their own browser.
- **Data Egress**: Data flows strictly between the user's browser and the chosen search engine. No telemetry sent to NumberShield.
- **Verdict**: **Adopted as highest-reliability zero-cost discovery workflow**.

### E. User-Authorized Local Email (MBOX) & SMS Parsers
- **What it discovers**: Real-world unwanted marketing subscriptions, commercial newsletters, SMS shortcodes (e.g., 5-6 digit codes like `223344`), opt-out instructions ("Reply STOP to cancel"), and `List-Unsubscribe` headers (mailto/http).
- **Cost**: 100% free.
- **Credentials**: None.
- **Quotas**: Unlimited local parsing.
- **Data Egress**: **Zero**. File contents are parsed in local Python memory and never transmitted over the network.
- **Verdict**: **Adopted as local-first high-fidelity subscription discovery engine**.

### F. Public Directory Remediation Registry
- **What it discovers**: Resolves known broker domains (e.g., FastPeopleSearch, TruePeopleSearch, Whitepages, Radaris, Spokeo, Nuwber, CyberBackgroundChecks) to verified, official opt-out URLs, suppression submission forms, expected turnaround times (24-72 hours), and required evidence.
- **Cost**: 100% free.
- **Credentials**: None required by NumberShield.
- **Quotas**: N/A (User completes official form).
- **Data Egress**: None from the app; user communicates directly with official broker opt-out portals.
- **Verdict**: **Adopted as core Remediation Hub**.

### G. National Telecom DND & Regulatory Channels
- **What it discovers / remediates**: Official statutory protections and complaint mechanisms:
  - US FTC Do Not Call (`donotcall.gov`) & FCC complaint center.
  - UK Telephone Preference Service (`tpsonline.org.uk`) & ICO nuisance reporting.
  - India TRAI 1909 DND & UCC Complaint SMS protocol (`COMP TEL NO XXXXXXXXXX, dd/mm/yy, Time`).
  - Canada CRTC National DNCL (`lnnte-dncl.gc.ca`) & Spam Reporting Centre.
  - Australia ACMA Do Not Call Register (`donotcall.gov.au`).
  - Carrier 7726 SPAM forwarding guidelines.
- **Cost**: 100% free government / public service.
- **Verdict**: **Adopted into Prevention Engine**.

---

## 3. Evaluated & Excluded Sources (With Rationale)

1. **Direct Data Broker HTML Scraping**:
   - *Why rejected*: Sites like FastPeopleSearch and TruePeopleSearch employ Cloudflare Turnstile and Datadome bot mitigation. Automating bypass scripts requires CAPTCHA-breaking services (paid) or fragile headless browser hacks that violate terms and break unpredictably. Instead, NumberShield uses search index discovery + direct assisted opt-out.
2. **SpiderFoot**:
   - *Why rejected*: Heavily bloated dependency graph, requires dozens of paid API keys (Shodan, Hunter, FullContact, Pipl) to achieve useful results, and leaks queries across unverified third parties.
3. **HaveIBeenPwned Automated Phone Checks**:
   - *Why rejected*: HIBP's public API does not offer a free arbitrary phone-number exposure endpoint. HIBP phone data was historically limited to the 2021 Facebook scraping dataset and required specific web interface lookups. Claiming to query HIBP for free phone exposure via API would be a fabrication.
4. **Commercial Phone Intelligence APIs (Numverify, Twilio Lookup, Telesign)**:
   - *Why rejected*: Violates the zero-cost requirement. Even free tiers require credit card registration, expire quickly, or cap requests at 50-100 total calls. Libphonenumber provides 90% of carrier/format metadata locally at zero cost.

---

## 4. Coverage Summary

| Engine Area | Free / Local Mechanism | External Dependency | Coverage Gap Disclosed |
| :--- | :--- | :--- | :--- |
| **Telephony Parsing** | `phonenumbers` (libphonenumber) | None | Does not reveal active live SIM status or prepaid/postpaid billing. |
| **Web Discovery** | SearXNG + DDG Lite + Manual Dorks | Public search engines | Deep web, private social networks (WhatsApp, Telegram), and paywalled directories. |
| **Subscriptions** | Local MBOX & SMS XML/JSON parsing | Local files | Only covers services present in user's exported communication records. |
| **Remediation** | Registry of 25+ official opt-out portals | Official portals | Requires user action for CAPTCHA/email verification steps; data brokers may re-scrape public records later. |
| **Spam Prevention** | Local incident log + DND guides + 7726 | Regulatory registries | Cannot prevent spoofed VoIP calls originating from outside national jurisdiction. |
