"""Discovery search providers package."""
from backend.app.engines.discovery.providers.base import (
    SearchProvider,
    ProviderResult,
    ProviderOutcome,
    ProviderStatus,
    SearchExecutionResult,
)
from backend.app.engines.discovery.providers.searxng import SearXNGProvider
from backend.app.engines.discovery.providers.duckduckgo import DuckDuckGoProvider
from backend.app.engines.discovery.providers.wikimedia import WikimediaProvider
from backend.app.engines.discovery.providers.hackernews import HackerNewsProvider
from backend.app.engines.discovery.providers.manual_dorks import generate_manual_dorks, ManualDork

__all__ = [
    "SearchProvider",
    "ProviderResult",
    "ProviderOutcome",
    "ProviderStatus",
    "SearchExecutionResult",
    "SearXNGProvider",
    "DuckDuckGoProvider",
    "WikimediaProvider",
    "HackerNewsProvider",
    "generate_manual_dorks",
    "ManualDork",
]
