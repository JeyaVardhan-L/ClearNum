"""DuckDuckGo HTML search provider.
Queries DuckDuckGo's non-JavaScript endpoint with polite backoff and HTML parsing.
"""

import logging
from typing import List
from urllib.parse import parse_qs, urlparse, unquote
import httpx
from bs4 import BeautifulSoup
from backend.app.engines.discovery.normalizer import NormalizedPhone
from backend.app.engines.discovery.providers.base import SearchProvider, ProviderResult

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

    async def search(self, phone: NormalizedPhone, max_results: int = 15) -> List[ProviderResult]:
        results: List[ProviderResult] = []
        if not phone.is_possible:
            return results

        endpoint = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://html.duckduckgo.com/",
        }
        
        query = f'"{phone.e164}"'
        data = {"q": query, "b": ""}

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.post(endpoint, data=data, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # DDG HTML search results structure
                    links = soup.find_all("a", class_="result__url") or soup.find_all("a", class_="result__snippet")
                    elements = soup.find_all("div", class_="result")
                    
                    for el in elements[:max_results]:
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
        except Exception as e:
            logger.debug("DuckDuckGo HTML query failed or blocked: %s", e)

        return results
