"""Internet Archive Wayback Machine CDX Server Search Provider.
Uses the official, unauthenticated CDX Server API provided by the Internet Archive
to discover historical web snapshots, public pastes, and archived directory pages
referencing telephone numbers without requiring API keys or commercial subscriptions.
"""

import logging
import time
from typing import List
from urllib.parse import urlparse
import httpx

from backend.app.core.security import mask_phone_number
from backend.app.core.ssrf import validate_url_safe, SSRFSafeTransport
from backend.app.engines.discovery.normalizer import NormalizedPhone
from backend.app.engines.discovery.providers.base import (
    SearchProvider,
    ProviderResult,
    ProviderStatus,
    ProviderOutcome,
    SearchExecutionResult,
)

logger = logging.getLogger(__name__)


def format_archive_date(ts: str) -> str:
    """Formats an archive 14-digit timestamp YYYYMMDDhhmmss into YYYY-MM-DD."""
    if len(ts) >= 8:
        return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
    return ts


class WaybackProvider(SearchProvider):
    provider_id: str = "wayback"
    name: str = "Internet Archive (Wayback CDX)"
    is_free: bool = True
    requires_auth: bool = False

    def __init__(self, endpoint: str = "https://web.archive.org/cdx/search/cdx", timeout: float = 8.0):
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

        search_digits = phone.digits_only if phone.digits_only else phone.e164.lstrip("+")
        params = {
            "url": f"*{search_digits}*",
            "output": "json",
            "fl": "original,timestamp,mimetype,statuscode",
            "limit": str(max_results),
            "collapse": "urlkey",
            "filter": "statuscode:200",
        }

        headers = {
            "User-Agent": "NumberShield/1.0 (Privacy Exposure Scanner; local open-source; archive research)",
            "Accept": "application/json",
        }

        masked = mask_phone_number(phone.e164)
        logger.info(f"Querying Internet Archive CDX API for {masked}")

        try:
            validate_url_safe(self.endpoint)
            transport = SSRFSafeTransport(verify=True)
            async with httpx.AsyncClient(transport=transport, timeout=self.timeout, follow_redirects=False, trust_env=False) as client:
                resp = await client.get(self.endpoint, params=params, headers=headers)
                duration_ms = int((time.perf_counter() - start_time) * 1000)

                if resp.status_code == 429:
                    logger.warning(f"Wayback CDX API rate limited (HTTP 429) for {masked}")
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.RATE_LIMITED,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=True,
                        diagnostic="Internet Archive CDX API rate limited (HTTP 429)",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                if resp.status_code != 200:
                    logger.warning(f"Wayback CDX API returned HTTP {resp.status_code}")
                    outcome = ProviderOutcome(
                        provider_id=self.provider_id,
                        status=ProviderStatus.UNREACHABLE,
                        result_count=0,
                        duration_ms=duration_ms,
                        retryable=True,
                        diagnostic=f"Wayback CDX API returned HTTP {resp.status_code}",
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
                        diagnostic="Wayback CDX response was not valid JSON",
                    )
                    return SearchExecutionResult(results=[], outcome=outcome)

                if isinstance(data, list) and len(data) > 0:
                    # Check if first row is header row
                    rows = data
                    if rows and rows[0] and rows[0][0] == "original":
                        rows = rows[1:]

                    for row in rows:
                        if not isinstance(row, list) or len(row) == 0:
                            continue
                        original_url = str(row[0]).strip()
                        if not original_url:
                            continue
                        timestamp = str(row[1]).strip() if len(row) > 1 else ""
                        formatted_date = format_archive_date(timestamp)
                        archive_view_url = (
                            f"https://web.archive.org/web/{timestamp}/{original_url}"
                            if timestamp
                            else original_url
                        )
                        parsed_orig = urlparse(original_url)
                        orig_domain = parsed_orig.netloc.lower().replace("www.", "") or "archive-record"

                        title = f"Archived Snapshot — {orig_domain} ({formatted_date})"
                        snippet = (
                            f"Historical capture on {formatted_date} indexing telephone digits "
                            f"at original location: {original_url}"
                        )

                        results.append(
                            ProviderResult.from_url_and_title(
                                url=archive_view_url,
                                title=title,
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
                    diagnostic=f"Successfully queried Wayback CDX ({len(results)} snapshots)",
                    last_successful_check=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
                return SearchExecutionResult(results=results, outcome=outcome)

        except (httpx.TimeoutException, httpx.NetworkError) as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"Wayback CDX API network error: {type(e).__name__}")
            outcome = ProviderOutcome(
                provider_id=self.provider_id,
                status=ProviderStatus.UNREACHABLE,
                result_count=0,
                duration_ms=duration_ms,
                retryable=True,
                diagnostic=f"Wayback CDX API unreachable: {type(e).__name__}",
            )
            return SearchExecutionResult(results=[], outcome=outcome)
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.exception(f"Unexpected error querying Wayback CDX API: {e}")
            outcome = ProviderOutcome(
                provider_id=self.provider_id,
                status=ProviderStatus.MALFORMED_RESPONSE,
                result_count=0,
                duration_ms=duration_ms,
                retryable=False,
                diagnostic=f"Unexpected error: {type(e).__name__}",
            )
            return SearchExecutionResult(results=[], outcome=outcome)
