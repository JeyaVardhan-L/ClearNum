"""SearXNG meta-search provider.
Queries public or self-hosted SearXNG instances using the open JSON search API
with structured health and failure observability.
"""

import json
import logging
import time
from typing import List
from urllib.parse import urlparse
import httpx
from backend.app.core.config import settings
from backend.app.core.security import mask_phone_number
from backend.app.core.ssrf import validate_url_safe, SSRFSafeTransport, SSRFValidationError
from backend.app.engines.discovery.normalizer import NormalizedPhone
from backend.app.engines.discovery.providers.base import (
    SearchProvider,
    ProviderResult,
    ProviderStatus,
    ProviderOutcome,
    SearchExecutionResult,
)

logger = logging.getLogger(__name__)

# Primary vetting fallbacks when no local instance configured
FALLBACK_INSTANCES = [
    "https://priv.au",
    "https://searx.tiekoetter.com",
    "https://searxng.site",
]


class SearXNGProvider(SearchProvider):
    provider_id: str = "searxng"
    name: str = "SearXNG Meta-Search"
    is_free: bool = True
    requires_auth: bool = False

    def __init__(self, instance_url: str | None = None):
        self.instance_url = instance_url or settings.searxng_instance

    async def search(self, phone: NormalizedPhone, max_results: int = 15) -> SearchExecutionResult:
        start_time = time.perf_counter()
        results: List[ProviderResult] = []

        if not phone.is_possible or not phone.e164:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            outcome = ProviderOutcome(
                provider_id=self.provider_id,
                status=ProviderStatus.UNSUPPORTED,
                result_count=0,
                duration_ms=duration_ms,
                retryable=False,
                diagnostic="Phone number is not possible or missing canonical E.164 representation",
            )
            return SearchExecutionResult(results=[], outcome=outcome)

        instances = [self.instance_url] if self.instance_url else FALLBACK_INSTANCES
        if not instances or not instances[0]:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            outcome = ProviderOutcome(
                provider_id=self.provider_id,
                status=ProviderStatus.UNCONFIGURED,
                result_count=0,
                duration_ms=duration_ms,
                retryable=False,
                diagnostic="No SearXNG instance configured (set SEARXNG_INSTANCE_URL in environment)",
            )
            return SearchExecutionResult(results=[], outcome=outcome)

        query = f'"{phone.e164}"'
        last_status = ProviderStatus.UNREACHABLE
        last_diagnostic = "All attempted SearXNG endpoints failed or were unreachable"

        # Try configured instance or first accessible fallback (bounded, polite, no evasive hammering)
        for base_url in instances[:3]:
            clean_base = base_url.rstrip("/")
            endpoint = f"{clean_base}/search"
            is_configured_local = bool(self.instance_url and clean_base == self.instance_url.rstrip("/"))
            parsed_host = urlparse(clean_base).netloc.lower().split(":")[0].strip("[]")
            allow_loopback = is_configured_local and (parsed_host in ("127.0.0.1", "localhost", "::1"))

            try:
                # SSRF validate instance endpoint
                validate_url_safe(endpoint, allow_loopback=allow_loopback)
                params = {
                    "q": query,
                    "format": "json",
                    "language": "all",
                }

                transport = SSRFSafeTransport(verify=True, allow_loopback=allow_loopback)
                async with httpx.AsyncClient(transport=transport, timeout=8.0, follow_redirects=False, trust_env=False) as client:
                    resp = await client.get(endpoint, params=params)
                    duration_ms = int((time.perf_counter() - start_time) * 1000)

                    if resp.status_code == 429:
                        last_status = ProviderStatus.RATE_LIMITED
                        last_diagnostic = (
                            f"SearXNG instance ({urlparse(clean_base).netloc}) returned HTTP 429 (Rate Limited). "
                            "Public instances enforce strict anti-scraping limits. Use Direct Search Dorks or run a local SearXNG container."
                        )
                        continue

                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                        except (json.JSONDecodeError, ValueError):
                            last_status = ProviderStatus.MALFORMED_RESPONSE
                            last_diagnostic = f"SearXNG instance ({urlparse(clean_base).netloc}) returned invalid non-JSON payload."
                            continue

                        if not isinstance(data, dict):
                            last_status = ProviderStatus.MALFORMED_RESPONSE
                            last_diagnostic = f"SearXNG instance ({urlparse(clean_base).netloc}) returned non-dictionary response."
                            continue

                        raw_results = data.get("results", [])
                        for item in raw_results[:max_results]:
                            url = item.get("url")
                            title = item.get("title", "")
                            content = item.get("content", "")
                            if url and url.startswith(("http://", "https://")):
                                results.append(ProviderResult.from_url_and_title(
                                    url=url,
                                    title=title,
                                    snippet=content,
                                    provider_id=self.provider_id,
                                ))

                        outcome = ProviderOutcome(
                            provider_id=self.provider_id,
                            status=ProviderStatus.HEALTHY,
                            result_count=len(results),
                            duration_ms=duration_ms,
                            retryable=False,
                            diagnostic=(
                                f"SearXNG query succeeded via {urlparse(clean_base).netloc} ({len(results)} matches)"
                                if results
                                else f"SearXNG query succeeded via {urlparse(clean_base).netloc} (zero matches)"
                            ),
                            last_successful_check=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        )
                        return SearchExecutionResult(results=results, outcome=outcome)

                    last_status = ProviderStatus.UNREACHABLE
                    last_diagnostic = f"SearXNG instance ({urlparse(clean_base).netloc}) returned HTTP {resp.status_code}"

            except Exception as e:
                masked = mask_phone_number(phone.e164)
                logger.debug("SearXNG instance %s error for identity [%s]: %s", urlparse(clean_base).netloc, masked, type(e).__name__)
                last_status = ProviderStatus.UNREACHABLE
                last_diagnostic = f"Could not connect to SearXNG instance ({urlparse(clean_base).netloc})"

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        outcome = ProviderOutcome(
            provider_id=self.provider_id,
            status=last_status,
            result_count=len(results),
            duration_ms=duration_ms,
            retryable=(last_status in (ProviderStatus.RATE_LIMITED, ProviderStatus.UNREACHABLE)),
            diagnostic=last_diagnostic,
        )
        return SearchExecutionResult(results=results, outcome=outcome)
