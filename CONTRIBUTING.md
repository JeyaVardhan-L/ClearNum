# Contributing to NumberShield

Thank you for your interest in contributing to **NumberShield**!

NumberShield is a free, open-source, zero-cost, local-first privacy platform designed to help people discover and remediate phone-number exposures while combating unsolicited telemarketing spam.

---

## 1. Core Principles for Contributors

All contributions must adhere to our non-negotiable constraints:
1. **Zero Mandatory Cost**: No paid API keys, paid hosting services, or mandatory commercial subscriptions.
2. **Local-First & Zero Egress**: All parsing, normalization, and local file analysis must execute on the user's local machine (`127.0.0.1`).
3. **No Credential Stealing or Scraping Violations**: We do not bypass CAPTCHAs, violate website terms of service, or simulate fake API successes.
4. **Phone Privacy**: Never commit real people's phone numbers to git history, test fixtures, or documentation. Use RFC 5737 / ITU-T fictional numbers (e.g., `+1 555-0100` to `+1 555-0199` or `+1 415-555-2671`).
5. **Truthful Lifecycles**: Do not present optimistic or fake metrics. An action is only `VERIFIED_REMOVED` when confirmed by automated rescan or verified evidence.

---

## 2. Development Setup

### Backend (Python 3.10+)
```bash
# Create virtual environment
uv venv .venv
.venv\Scripts\activate  # Windows
# or source .venv/bin/activate  # Linux/macOS

# Install dependencies
uv pip install -e .
```

### Frontend (Node 20+)
```bash
cd frontend
npm install
npm run dev
```

### Running Tests
```bash
# Run backend test suite
pytest -v

# Run Playwright end-to-end tests
pytest -v tests/test_e2e_playwright.py
```

---

## 3. Pull Request Guidelines

1. Ensure all unit and integration tests pass.
2. Include unit tests for any new normalizer rules, search providers, or remediation registry entries.
3. Keep code cleanly typed with Pydantic v2 and TypeScript.
4. Document all source limitations in `docs/source-capability-matrix.md`.
