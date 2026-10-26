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
from backend.app.engines.discovery.providers.manual_dorks import generate_manual_dorks, ManualDork

__all__ = [
    "SearchProvider",
    "ProviderResult",
    "ProviderOutcome",
    "ProviderStatus",
    "SearchExecutionResult",
    "SearXNGProvider",
    "DuckDuckGoProvider",
    "generate_manual_dorks",
    "ManualDork",
]
