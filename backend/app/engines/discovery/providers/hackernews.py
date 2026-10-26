"""Hacker News Algolia Search Provider.
Uses the official, free Algolia Search API for Hacker News to discover public discussions,
comments, and hiring thread disclosures of phone numbers without requiring API keys or scraping.
"""

import logging
import time
import re
from typing import List
import httpx

from backend.app.core.security import mask_phone_number
from backend.app.engines.discovery.normalizer import NormalizedPhone
from backend.app.engines.discovery.providers.base import (
    SearchProvider,
    ProviderResult,
    ProviderStatus,
    ProviderOutcome,
    SearchExecutionResult,
)

logger = logging.getLogger(__name__)


def clean_html_snippet(raw_text: str) -> str:
    """Cleans HTML tags from Algolia comment or story texts."""
    if not raw_text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", raw_text)
    return " ".join(cleaned.split()).strip()


class HackerNewsProvider(SearchProvider):
    provider_id: str = "hackernews"
    name: str = "Hacker News (Algolia API)"
    is_free: bool = True
    requires_auth: bool = False

    def __init__(self, endpoint: str = "https://hn.algolia.com/api/v1/search", timeout: float = 8.0):
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

        queries = phone.query_permutations if hasattr(phone, "query_permutations") and phone.query_permutations else [f'"{phone.e164}"']
        primary_query = queries[0] if queries else f'"{phone.e164}"'

        params = {
            "query": primary_query,
            "tags": "comment,story",
            "hitsPerPage": str(max_results),
        }

        headers = {
            "User-Agent": "NumberShield/1.0 (Privacy Exposure Scanner; local open-source)",
            "Accept": "application/json",
        }

        masked = mask_phone_number(phone.e164)
        logger.info(f"Querying Hacker News Algolia API for {masked}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(self.endpoint, params=params, headers=headers)

                duration_ms = int((time.perf_counter() - start_time) * 1000)

                if resp.status_code == 429:
                    logger.warning(f"Hacker News Algolia API rate limited (HTTP 429) for {masked}")
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.RATE_LIMITED,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=True,
                        diagnostic="Hacker News API rate limit exceeded (HTTP 429)",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                if resp.status_code != 200:
                    logger.warning(f"Hacker News API returned HTTP {resp.status_code}")
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.UNREACHABLE,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=True,
                        diagnostic=f"Hacker News API returned HTTP {resp.status_code}",
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
                        diagnostic="Hacker News response was not valid JSON",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                hits = data.get("hits", [])
                for hit in hits:
                    object_id = hit.get("objectID")
                    if not object_id:
                        continue
                    item_url = f"https://news.ycombinator.com/item?id={object_id}"
                    author = hit.get("author", "unknown")
                    story_title = hit.get("story_title") or hit.get("title") or f"Comment by {author}"
                    snippet_raw = hit.get("comment_text") or hit.get("story_text") or ""
                    snippet = clean_html_snippet(snippet_raw)

                    results.append(
                        ProviderResult.from_url_and_title(
                            url=item_url,
                            title=f"Hacker News — {story_title}",
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
                    diagnostic=f"Successfully queried Hacker News ({len(results)} hits)",
                    last_successful_check=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
                return SearchExecutionResult(results=results, outcome=outcome)

        except (httpx.TimeoutException, httpx.NetworkError) as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"Hacker News API network error: {type(e).__name__}")
            outcome = ProviderOutcome(
                provider_id=self.provider_id,
                status=ProviderStatus.UNREACHABLE,
                result_count=0,
                duration_ms=duration_ms,
                retryable=True,
                diagnostic=f"Hacker News API unreachable: {type(e).__name__}",
            )
            return SearchExecutionResult(results=[], outcome=outcome)
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.exception(f"Unexpected error querying Hacker News: {e}")
            outcome = ProviderOutcome(
                provider_id=self.provider_id,
                status=ProviderStatus.MALFORMED_RESPONSE,
                result_count=0,
                duration_ms=duration_ms,
                retryable=False,
                diagnostic=f"Unexpected error: {type(e).__name__}",
            )
            return SearchExecutionResult(results=[], outcome=outcome)
