"""SearXNG meta-search provider.
Queries public or self-hosted SearXNG instances using the open JSON search API.
"""

import logging
from typing import List
import httpx
from backend.app.core.config import settings
from backend.app.core.ssrf import validate_url_safe
from backend.app.engines.discovery.normalizer import NormalizedPhone
from backend.app.engines.discovery.providers.base import SearchProvider, ProviderResult

logger = logging.getLogger(__name__)

# List of vetted public instances if none configured locally
FALLBACK_INSTANCES = [
    "https://priv.au",
    "https://search.ononoki.org",
    "https://searx.tiekoetter.com",
]


class SearXNGProvider(SearchProvider):
    provider_id: str = "searxng"
    name: str = "SearXNG Meta-Search"
    is_free: bool = True
    requires_auth: bool = False

    def __init__(self, instance_url: str | None = None):
        self.instance_url = instance_url or settings.searxng_instance

    async def search(self, phone: NormalizedPhone, max_results: int = 15) -> List[ProviderResult]:
        results: List[ProviderResult] = []
        if not phone.is_possible:
            return results

        instances = [self.instance_url] if self.instance_url else FALLBACK_INSTANCES
        query = f'"{phone.e164}"'

        for base_url in instances:
            if not base_url:
                continue
            endpoint = f"{base_url.rstrip('/')}/search"
            try:
                # SSRF validate instance endpoint
                validate_url_safe(endpoint)
                params = {
                    "q": query,
                    "format": "json",
                    "language": "all",
                }
                async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                    resp = await client.get(endpoint, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
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
                        if results:
                            break  # Successfully obtained results
            except Exception as e:
                logger.debug("SearXNG instance %s failed or timed out: %s", base_url, e)
                continue

        return results
