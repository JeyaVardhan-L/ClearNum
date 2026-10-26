"""Abstract base class and data structures for discovery SearchProviders."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List
from urllib.parse import urlparse
from backend.app.engines.discovery.normalizer import NormalizedPhone


@dataclass
class ProviderResult:
    url: str
    title: str
    domain: str
    snippet: str
    provider_id: str

    @classmethod
    def from_url_and_title(cls, url: str, title: str, snippet: str, provider_id: str) -> "ProviderResult":
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return cls(
            url=url,
            title=title.strip() if title else domain,
            domain=domain,
            snippet=snippet.strip() if snippet else "",
            provider_id=provider_id,
        )


class SearchProvider(ABC):
    provider_id: str
    name: str
    is_free: bool = True
    requires_auth: bool = False

    @abstractmethod
    async def search(self, phone: NormalizedPhone, max_results: int = 15) -> List[ProviderResult]:
        """Executes a search for the normalized phone variants.
        Must handle its own timeouts, rate-limits, and partial failures.
        """
        pass
