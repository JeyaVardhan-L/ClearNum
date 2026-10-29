"""DuckDuckGo HTML search provider.
Queries DuckDuckGo's non-JavaScript endpoint with polite backoff, HTML parsing,
and structured outcome reporting.
"""

import logging
import time
from typing import List
from urllib.parse import parse_qs, urlparse, unquote
import httpx
from bs4 import BeautifulSoup
from backend.app.core.security import mask_phone_number
from backend.app.core.ssrf import SSRFSafeTransport
from backend.app.engines.discovery.normalizer import NormalizedPhone
from backend.app.engines.discovery.providers.base import (
    SearchProvider,
    ProviderResult,
    ProviderStatus,
    ProviderOutcome,
    SearchExecutionResult,
)

logger = logging.getLogger(__name__)


def clean_ddg_redirect(raw_url: str) -> str:
    """Extracts the direct target URL from DuckDuckGo redirect paths (/l/?uddg=...)."""
    if not raw_url:
        return ""
    if "/l/?uddg=" in raw_url:
        parsed = urlparse(raw_url)
        params = parse_qs(parsed.query)
        if "uddg" in params and params["uddg"]:
            return unquote(params["uddg"][0])
    return raw_url


class DuckDuckGoProvider(SearchProvider):
    provider_id: str = "duckduckgo"
    name: str = "DuckDuckGo Web"
    is_free: bool = True
    requires_auth: bool = False

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

        endpoint = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://html.duckduckgo.com/",
        }

        # Use canonical E.164 query for public engine
        query = f'"{phone.e164}"'
        data = {"q": query, "b": ""}

        try:
            transport = SSRFSafeTransport(verify=True)
            async with httpx.AsyncClient(transport=transport, timeout=8.0, follow_redirects=False, trust_env=False) as client:
                resp = await client.post(endpoint, data=data, headers=headers)
                duration_ms = int((time.perf_counter() - start_time) * 1000)

                if resp.status_code == 429:
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.RATE_LIMITED,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=True,
                        diagnostic="DuckDuckGo returned HTTP 429 (Rate Limited). Respecting backoff.",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                if resp.status_code == 202:
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.RATE_LIMITED,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=True,
                        diagnostic="DuckDuckGo presented anti-bot challenge (HTTP 202). Use Direct Search Dorks for browser search.",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                if resp.status_code != 200:
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.UNREACHABLE,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=True,
                        diagnostic=f"DuckDuckGo search endpoint returned unexpected status HTTP {resp.status_code}",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                html_text = resp.text
                lower_html = html_text.lower()

                # Check for anti-bot or CAPTCHA anomaly challenge
                if "anomaly" in lower_html or "captcha" in lower_html or "bots use duckduckgo" in lower_html:
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.RATE_LIMITED,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=True,
                        diagnostic="DuckDuckGo presented automated request verification challenge. Use Direct Search Dorks.",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                soup = BeautifulSoup(html_text, "html.parser")
                elements = soup.find_all("div", class_="result")

                for el in elements[:max_results]:
                    # Exclude the "no-results" placeholder div
                    if "result--no-result" in el.get("class", []):
                        continue

                    title_el = el.find("a", class_="result__a")
                    snippet_el = el.find("a", class_="result__snippet") or el.find("div", class_="result__snippet")
                    url_el = el.find("a", class_="result__url")

                    raw_href = title_el.get("href") if title_el else (url_el.get("href") if url_el else None)
                    if not raw_href:
                        continue

                    clean_url = clean_ddg_redirect(raw_href)
                    if clean_url.startswith(("http://", "https://")):
                        title = title_el.get_text(strip=True) if title_el else ""
                        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                        results.append(ProviderResult.from_url_and_title(
                            url=clean_url,
                            title=title,
                            snippet=snippet,
                            provider_id=self.provider_id,
                        ))

                outcome = ProviderOutcome(
                    provider_id=self.provider_id,
                    status=ProviderStatus.HEALTHY,
                    result_count=len(results),
                    duration_ms=duration_ms,
                    retryable=False,
                    diagnostic=(
                        f"Search completed successfully ({len(results)} matches returned)"
                        if results
                        else "Search completed successfully (zero public exposures indexed)"
                    ),
                    last_successful_check=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
                return SearchExecutionResult(results=results, outcome=outcome)

        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            outcome = ProviderOutcome(
                provider_id=self.provider_id,
                status=ProviderStatus.UNREACHABLE,
                result_count=0,
                duration_ms=duration_ms,
                retryable=True,
                diagnostic="DuckDuckGo connection timed out after 8.0s",
            )
            return SearchExecutionResult(results=[], outcome=outcome)

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            masked = mask_phone_number(phone.e164)
            logger.debug("DuckDuckGo search failed for identity [%s]: %s", masked, type(exc).__name__)
            outcome = ProviderOutcome(
                provider_id=self.provider_id,
                status=ProviderStatus.UNREACHABLE,
                result_count=0,
                duration_ms=duration_ms,
                retryable=True,
                diagnostic="Unable to reach DuckDuckGo search service",
            )
            return SearchExecutionResult(results=[], outcome=outcome)
