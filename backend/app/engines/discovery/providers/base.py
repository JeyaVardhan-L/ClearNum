"""Abstract base class and data structures for discovery SearchProviders.
Provides structured outcomes, health observability, and backward-compatible results.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from urllib.parse import urlparse
from backend.app.engines.discovery.normalizer import NormalizedPhone


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    RATE_LIMITED = "rate_limited"
    UNREACHABLE = "unreachable"
    UNCONFIGURED = "unconfigured"
    MALFORMED_RESPONSE = "malformed_response"
    UNSUPPORTED = "unsupported"


@dataclass
class ProviderOutcome:
    provider_id: str
    status: ProviderStatus
    result_count: int
    duration_ms: int
    retryable: bool
    diagnostic: str
    last_successful_check: Optional[str] = None


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


@dataclass
class SearchExecutionResult:
    """Backward-compatible container holding both search results and the provider's execution outcome."""
    results: List[ProviderResult] = field(default_factory=list)
    outcome: Optional[ProviderOutcome] = None

    def __iter__(self):
        return iter(self.results)

    def __len__(self):
        return len(self.results)

    def __getitem__(self, item):
        return self.results[item]

    def append(self, item: ProviderResult):
        self.results.append(item)

    def extend(self, items):
        self.results.extend(items)


class SearchProvider(ABC):
    provider_id: str
    name: str
    is_free: bool = True
    requires_auth: bool = False

    @abstractmethod
    async def search(self, phone: NormalizedPhone, max_results: int = 15) -> SearchExecutionResult:
        """Executes a search for the normalized phone variants.
        Must handle its own timeouts, rate-limits, and return a structured ProviderOutcome.
        """
        pass
