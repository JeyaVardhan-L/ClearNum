# NumberShield — Guide: Adding a Source or Remediation Pathway

This guide explains how to extend **NumberShield** with new search providers, local file parsers, and remediation registry sources without touching the core system.

---

## 1. Adding a Discovery `SearchProvider`

All search providers implement the abstract class `SearchProvider` located in `backend/app/engines/discovery/providers/base.py`.

### Step 1: Subclass `SearchProvider`

```python
from typing import List
from backend.app.engines.discovery.providers.base import SearchProvider, ProviderResult
from backend.app.engines.discovery.normalizer import NormalizedPhone

class MyCustomProvider(SearchProvider):
    provider_id: str = "my_custom_engine"
    name: str = "My Custom Search Engine"
    is_free: bool = True
    requires_auth: bool = False
    
    async def search(self, phone: NormalizedPhone, max_results: int = 20) -> List[ProviderResult]:
        results = []
        # Query your zero-cost, legal source using phone.variants (e.g. phone.e164, phone.national)
        # Handle timeouts and parse results safely
        return results
```

### Step 2: Register in `provider_manager.py`

Add your provider class to the default active providers list in `backend/app/engines/discovery/providers/__init__.py`.

---

## 2. Adding a Data Broker or Directory to the Remediation Registry

The source registry is located at `backend/app/engines/remediation/registry.py`.

### Step 1: Define the Source Entry

```python
SourceDefinition(
    source_id="example_directory",
    name="Example People Search",
    category="data_broker",  # "data_broker", "search_engine", "public_paste", "telecom"
    domains=["exampledirectory.com", "example-people.net"],
    official_removal_url="https://www.exampledirectory.com/opt-out",
    removal_method="online_form",  # "online_form", "email_request", "assisted_mail", "telecom_dnd"
    instructions=[
        "1. Search for your profile on Example Directory.",
        "2. Copy the full profile URL from your browser address bar.",
        "3. Paste the profile URL into the official opt-out form.",
        "4. Complete the email verification link sent to your inbox."
    ],
    processing_time_estimate="24-48 hours",
    requires_email_confirmation=True,
    requires_phone_call=False,
    statutory_rights=["CCPA", "GDPR"],
    contact_email="privacy@exampledirectory.com",
    notes="Verification link expires in 24 hours."
)
```

### Step 2: Unit Test the Entry

Add a test case in `tests/test_remediation_registry.py` asserting that domain matching, instruction rendering, and URL validity pass schema verification.

---

## 3. Adding a Regulatory Telecom DND Guide

To add a new national telecom regulatory complaint pathway, update `backend/app/engines/remediation/dnd_guides.py`:
1. Provide the official statutory registration portal (e.g., `donotcall.gov`).
2. Provide the SMS shortcode or carrier forwarding procedure (e.g., forwarding spam SMS to `7726`).
3. Document the formal complaint filing procedure with statutory deadlines.
