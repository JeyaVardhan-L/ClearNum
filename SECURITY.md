# Security Policy

## 1. Supported Versions

NumberShield is under active development. Only the current mainline release receives security patches.

| Version | Supported |
| :--- | :--- |
| 1.0.x | Yes |
| < 1.0.0 | No |

---

## 2. Reporting a Vulnerability

The NumberShield project welcomes responsible disclosure of security vulnerabilities. If you discover a security vulnerability or privacy flaw:

1. **Do not open a public GitHub issue.**
2. Send an email with detailed reproduction steps, proof of concept, and environment details to `security@numbershield.local` (or file a private security advisory on GitHub).
3. We will acknowledge receipt within 48 hours and work toward a coordinated patch release within 14 days.

---

## 3. Threat Assumptions & Out-of-Scope Behaviors

### In-Scope
- Server-Side Request Forgery (SSRF) bypasses allowing internal network probes.
- Regular expression denial of service (ReDoS) on telephone pattern matching.
- Leakage of unmasked telephone numbers into logs, stdout, or crash traces.
- Cross-Site Scripting (XSS) or DOM injection from parsed third-party HTML.
- Insecure storage or weak cryptographic key generation.

### Out-of-Scope
- Physical or administrative access to the user's unlocked computer.
- Network eavesdropping when running behind a misconfigured reverse proxy that disables HTTPS.
- Third-party websites changing their HTML structure or blocking web crawlers.
- Third-party data brokers failing to honor their own statutory privacy commitments.
