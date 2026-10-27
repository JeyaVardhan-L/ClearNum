"""Wikimedia / Wikipedia Public Document Discovery Provider.
Uses the official, free MediaWiki Action API to discover public document, talk page,
revision, and community leaks of phone numbers without requiring API keys or scraping.
"""

import logging
import time
import re
from typing import List
from urllib.parse import quote
import httpx

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


def clean_mediawiki_snippet(raw_snippet: str) -> str:
    """Removes HTML tags such as <span class="searchmatch"> from MediaWiki search snippets."""
    if not raw_snippet:
        return ""
    # Strip HTML tags
    cleaned = re.sub(r"<[^>]+>", "", raw_snippet)
    return " ".join(cleaned.split()).strip()


class WikimediaProvider(SearchProvider):
    provider_id: str = "wikimedia"
    name: str = "Wikipedia / Wikimedia Commons"
    is_free: bool = True
    requires_auth: bool = False

    def __init__(self, endpoint: str = "https://en.wikipedia.org/w/api.php", timeout: float = 8.0):
        self.endpoint = endpoint
        self.timeout = timeout

    async def search(self, phone: NormalizedPhone, max_results: int = 10) -> SearchExecutionResult:
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

        # Build exact query targeting canonical and national format
        queries = phone.query_permutations if hasattr(phone, "query_permutations") and phone.query_permutations else [f'"{phone.e164}"']
        primary_query = queries[0] if queries else f'"{phone.e164}"'

        params = {
            "action": "query",
            "list": "search",
            "srsearch": primary_query,
            "format": "json",
            "srlimit": str(max_results),
            "srprop": "snippet|titlesnippet|timestamp",
        }

        # Wikimedia User-Agent policy requires descriptive identification
        headers = {
            "User-Agent": "NumberShield/1.0 (Privacy Exposure Scanner; local open-source; contact: security@numbershield.local)",
            "Accept": "application/json",
        }

        masked = mask_phone_number(phone.e164)
        logger.info(f"Querying Wikimedia API for {masked}")

        try:
            validate_url_safe(self.endpoint)
            transport = SSRFSafeTransport(verify=True)
            async with httpx.AsyncClient(transport=transport, timeout=self.timeout, follow_redirects=False, trust_env=False) as client:
                resp = await client.get(self.endpoint, params=params, headers=headers)

                duration_ms = int((time.perf_counter() - start_time) * 1000)

                if resp.status_code == 429:
                    logger.warning(f"Wikimedia API rate limited (HTTP 429) for {masked}")
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.RATE_LIMITED,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=True,
                        diagnostic="Wikimedia API rate limit exceeded (HTTP 429)",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                if resp.status_code != 200:
                    logger.warning(f"Wikimedia API returned HTTP {resp.status_code}")
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.UNREACHABLE,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=True,
                        diagnostic=f"Wikimedia API returned HTTP {resp.status_code}",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                try:
                    data = resp.json()
                except Exception:
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.MALFORMED_RESPONSE,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=False,
                        diagnostic="Wikimedia response was not valid JSON",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                # Check for MediaWiki error structure
                if "error" in data:
                    err_info = data["error"].get("info", "Unknown MediaWiki error")
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.MALFORMED_RESPONSE,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=False,
                        diagnostic=f"MediaWiki error: {err_info}",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                search_hits = data.get("query", {}).get("search", [])
                for hit in search_hits:
                    title = hit.get("title", "")
                    if not title:
                        continue
                    wiki_slug = quote(title.replace(" ", "_"))
                    page_url = f"https://en.wikipedia.org/wiki/{wiki_slug}"
                    snippet = clean_mediawiki_snippet(hit.get("snippet", ""))

                    results.append(
                        ProviderResult.from_url_and_title(
                            url=page_url,
                            title=f"Wikipedia — {title}",
                            snippet=snippet,
                            provider_id=self.provider_id,
                        )
                    )

                outcome = ProviderOutcome(
                    provider_id=self.provider_id,
                    status=ProviderStatus.HEALTHY,
                    result_count=len(results),
                    duration_ms=duration_ms,
                    retryable=False,
                    diagnostic=f"Successfully queried Wikimedia ({len(results)} hits)",
                    last_successful_check=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
                return SearchExecutionResult(results=results, outcome=outcome)

        except (httpx.TimeoutException, httpx.NetworkError) as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"Wikimedia API network error: {type(e).__name__}")
            outcome = ProviderOutcome(
                provider_id=self.provider_id,
                status=ProviderStatus.UNREACHABLE,
                result_count=0,
                duration_ms=duration_ms,
                retryable=True,
                diagnostic=f"Wikimedia API unreachable: {type(e).__name__}",
            )
            return SearchExecutionResult(results=[], outcome=outcome)
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.exception(f"Unexpected error querying Wikimedia: {e}")
            outcome = ProviderOutcome(
                provider_id=self.provider_id,
                status=ProviderStatus.MALFORMED_RESPONSE,
                result_count=0,
                duration_ms=duration_ms,
                retryable=False,
                diagnostic=f"Unexpected error: {type(e).__name__}",
            )
            return SearchExecutionResult(results=[], outcome=outcome)
