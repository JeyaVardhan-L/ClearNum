"""Deterministic unit tests for Discovery Providers and Provider Outcomes."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from backend.app.engines.discovery.normalizer import parse_and_normalize
from backend.app.engines.discovery.providers import (
    DuckDuckGoProvider,
    SearXNGProvider,
    WikimediaProvider,
    HackerNewsProvider,
    WaybackProvider,
    ProviderStatus,
    ProviderOutcome,
    SearchExecutionResult,
)


@pytest.fixture
def valid_phone():
    return parse_and_normalize("+14155552671", "US")


@pytest.fixture
def invalid_phone():
    return parse_and_normalize("invalid", "US")


# --- DuckDuckGo Provider Tests ---

@pytest.mark.asyncio
async def test_ddg_healthy_with_results(valid_phone):
    fake_html = """
    <html><body>
    <div class="result">
        <a class="result__a" href="/l/?uddg=https%3A%2F%2Fpastebin.com%2Fxyz123">Pastebin leak</a>
        <a class="result__snippet">Found contact +14155552671 in database dump</a>
        <a class="result__url" href="https://pastebin.com/xyz123">pastebin.com/xyz123</a>
    </div>
    </body></html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_html

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        provider = DuckDuckGoProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 1
        assert res[0].url == "https://pastebin.com/xyz123"
        assert res.outcome is not None
        assert res.outcome.status == ProviderStatus.HEALTHY
        assert res.outcome.result_count == 1
        assert res.outcome.retryable is False
        assert "completed successfully" in res.outcome.diagnostic.lower()


@pytest.mark.asyncio
async def test_ddg_healthy_empty_search(valid_phone):
    fake_html = "<html><body><div class='results_zero'>No results found for query</div></body></html>"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_html

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        provider = DuckDuckGoProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome is not None
        assert res.outcome.status == ProviderStatus.HEALTHY
        assert res.outcome.result_count == 0
        assert "zero public exposures" in res.outcome.diagnostic.lower()


@pytest.mark.asyncio
async def test_ddg_rate_limited_http_429(valid_phone):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Too Many Requests"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        provider = DuckDuckGoProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome is not None
        assert res.outcome.status == ProviderStatus.RATE_LIMITED
        assert res.outcome.retryable is True
        assert "429" in res.outcome.diagnostic


@pytest.mark.asyncio
async def test_ddg_rate_limited_anti_bot_challenge(valid_phone):
    fake_html = "<html><body><h1>Anomaly Detected</h1><p>Bots use DuckDuckGo</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_html

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        provider = DuckDuckGoProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome is not None
        assert res.outcome.status == ProviderStatus.RATE_LIMITED
        assert res.outcome.retryable is True
        assert "challenge" in res.outcome.diagnostic.lower()


@pytest.mark.asyncio
async def test_ddg_unreachable_on_timeout(valid_phone):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.ConnectTimeout("Connection timed out")):
        provider = DuckDuckGoProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome is not None
        assert res.outcome.status == ProviderStatus.UNREACHABLE
        assert res.outcome.retryable is True
        assert "timed out" in res.outcome.diagnostic.lower()


@pytest.mark.asyncio
async def test_ddg_unsupported_on_invalid_phone(invalid_phone):
    provider = DuckDuckGoProvider()
    res = await provider.search(invalid_phone)
    assert len(res) == 0
    assert res.outcome is not None
    assert res.outcome.status == ProviderStatus.UNSUPPORTED
    assert res.outcome.retryable is False


# --- SearXNG Provider Tests ---

@pytest.mark.asyncio
async def test_searxng_healthy_with_results(valid_phone):
    mock_data = {
        "results": [
            {
                "url": "https://nuwber.com/person/5551234",
                "title": "Jane Doe Nuwber Record",
                "content": "Phone: +14155552671 located in San Francisco",
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data

    with patch("backend.app.engines.discovery.providers.searxng.validate_url_safe"):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            provider = SearXNGProvider(instance_url="https://searx.example.com")
            res = await provider.search(valid_phone)
            assert len(res) == 1
            assert res[0].url == "https://nuwber.com/person/5551234"
            assert res.outcome.status == ProviderStatus.HEALTHY
            assert res.outcome.result_count == 1
            assert res.outcome.retryable is False


@pytest.mark.asyncio
async def test_searxng_rate_limited_http_429(valid_phone):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Too Many Requests"

    with patch("backend.app.engines.discovery.providers.searxng.validate_url_safe"):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            provider = SearXNGProvider(instance_url="https://searx.example.com")
            res = await provider.search(valid_phone)
            assert len(res) == 0
            assert res.outcome.status == ProviderStatus.RATE_LIMITED
            assert res.outcome.retryable is True
            assert "429" in res.outcome.diagnostic


@pytest.mark.asyncio
async def test_searxng_malformed_response(valid_phone):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON")

    with patch("backend.app.engines.discovery.providers.searxng.validate_url_safe"):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            provider = SearXNGProvider(instance_url="https://searx.example.com")
            res = await provider.search(valid_phone)
            assert len(res) == 0
            assert res.outcome.status == ProviderStatus.MALFORMED_RESPONSE
            assert res.outcome.retryable is False


@pytest.mark.asyncio
async def test_searxng_unconfigured_when_no_instances(valid_phone):
    with patch("backend.app.engines.discovery.providers.searxng.FALLBACK_INSTANCES", []):
        provider = SearXNGProvider(instance_url="")
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome.status == ProviderStatus.UNCONFIGURED
        assert res.outcome.retryable is False
        assert "no searxng instance configured" in res.outcome.diagnostic.lower()


@pytest.mark.asyncio
async def test_searxng_unreachable_on_error(valid_phone):
    with patch("backend.app.engines.discovery.providers.searxng.validate_url_safe"):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("Connection refused")):
            provider = SearXNGProvider(instance_url="https://searx.example.com")
            res = await provider.search(valid_phone)
            assert len(res) == 0
            assert res.outcome.status == ProviderStatus.UNREACHABLE
            assert res.outcome.retryable is True


# --- Backwards-Compatibility Tests ---

def test_search_execution_result_backwards_compatible():
    container = SearchExecutionResult()
    assert len(container) == 0
    item = MagicMock(url="https://example.com")
    container.append(item)
    assert len(container) == 1
    assert container[0] == item
    # Test iteration
    for el in container:
        assert el.url == "https://example.com"


# --- Wikimedia Provider Tests ---

@pytest.mark.asyncio
async def test_wikimedia_healthy_with_results(valid_phone):
    fake_json = {
        "query": {
            "search": [
                {
                    "title": "Community Directory 2024",
                    "snippet": "Contact organizer at <span class=\"searchmatch\">+14155552671</span> for inquiry",
                    "timestamp": "2024-05-01T12:00:00Z",
                }
            ]
        }
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_json

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = WikimediaProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 1
        assert "Community_Directory_2024" in res[0].url
        assert "Wikipedia" in res[0].title
        assert res.outcome.status == ProviderStatus.HEALTHY
        assert res.outcome.result_count == 1
        assert "searchmatch" not in res[0].snippet


@pytest.mark.asyncio
async def test_wikimedia_rate_limited_http_429(valid_phone):
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = WikimediaProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome.status == ProviderStatus.RATE_LIMITED
        assert res.outcome.retryable is True


@pytest.mark.asyncio
async def test_wikimedia_unreachable_on_timeout(valid_phone):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Timeout")):
        provider = WikimediaProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome.status == ProviderStatus.UNREACHABLE
        assert res.outcome.retryable is True


@pytest.mark.asyncio
async def test_wikimedia_malformed_response(valid_phone):
    fake_err_json = {"error": {"info": "MediaWiki query syntax error"}}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_err_json

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = WikimediaProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome.status == ProviderStatus.MALFORMED_RESPONSE
        assert "MediaWiki error" in res.outcome.diagnostic


# --- Hacker News Provider Tests ---

@pytest.mark.asyncio
async def test_hackernews_healthy_with_results(valid_phone):
    fake_json = {
        "hits": [
            {
                "objectID": "9876543",
                "author": "alice_dev",
                "story_title": "Ask HN: Freelancer directory",
                "comment_text": "Reach me at <b>+14155552671</b> for contract work",
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_json

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = HackerNewsProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 1
        assert "item?id=9876543" in res[0].url
        assert "Ask HN: Freelancer directory" in res[0].title
        assert res.outcome.status == ProviderStatus.HEALTHY
        assert res.outcome.result_count == 1
        assert "<b>" not in res[0].snippet


@pytest.mark.asyncio
async def test_hackernews_rate_limited_http_429(valid_phone):
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = HackerNewsProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome.status == ProviderStatus.RATE_LIMITED
        assert res.outcome.retryable is True


@pytest.mark.asyncio
async def test_hackernews_unreachable_on_error(valid_phone):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("Network error")):
        provider = HackerNewsProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome.status == ProviderStatus.UNREACHABLE
        assert res.outcome.retryable is True


# --- Internet Archive Wayback CDX Provider Tests ---

@pytest.mark.asyncio
async def test_wayback_healthy_with_results(valid_phone):
    fake_cdx = [
        ["original", "timestamp", "mimetype", "statuscode"],
        ["https://pastebin.com/raw/4155552671", "20220412153000", "text/plain", "200"],
        ["https://directory.example.org/staff/4155552671", "20230115082000", "text/html", "200"],
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_cdx

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = WaybackProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 2
        assert "web.archive.org/web/20220412153000" in res[0].url
        assert "pastebin.com" in res[0].title
        assert "2022-04-12" in res[0].title
        assert res.outcome.status == ProviderStatus.HEALTHY
        assert res.outcome.result_count == 2
        assert res.outcome.retryable is False


@pytest.mark.asyncio
async def test_wayback_empty_results(valid_phone):
    fake_cdx = [["original", "timestamp", "mimetype", "statuscode"]]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_cdx

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = WaybackProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome.status == ProviderStatus.HEALTHY
        assert res.outcome.result_count == 0


@pytest.mark.asyncio
async def test_wayback_rate_limited_http_429(valid_phone):
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = WaybackProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome.status == ProviderStatus.RATE_LIMITED
        assert res.outcome.retryable is True


@pytest.mark.asyncio
async def test_wayback_unreachable_on_timeout(valid_phone):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Timeout")):
        provider = WaybackProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome.status == ProviderStatus.UNREACHABLE
        assert res.outcome.retryable is True


@pytest.mark.asyncio
async def test_wayback_malformed_json(valid_phone):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = WaybackProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome.status == ProviderStatus.MALFORMED_RESPONSE
        assert res.outcome.retryable is False


@pytest.mark.asyncio
async def test_wayback_unsupported_on_invalid_phone(invalid_phone):
    provider = WaybackProvider()
    res = await provider.search(invalid_phone)
    assert len(res) == 0
    assert res.outcome.status == ProviderStatus.UNSUPPORTED
    assert res.outcome.retryable is False


@pytest.mark.asyncio
async def test_ddg_rate_limited_http_202_challenge(valid_phone):
    mock_resp = MagicMock()
    mock_resp.status_code = 202
    mock_resp.text = "Challenge required"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        provider = DuckDuckGoProvider()
        res = await provider.search(valid_phone)
        assert len(res) == 0
        assert res.outcome is not None
        assert res.outcome.status == ProviderStatus.RATE_LIMITED
        assert res.outcome.retryable is True
        assert "202" in res.outcome.diagnostic


@pytest.mark.asyncio
async def test_searxng_fallback_on_429_tries_second_instance(valid_phone):
    # First instance returns 429, second instance returns 200 with result
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "Rate Limited"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "results": [
            {
                "url": "https://example.com/listing",
                "title": "Example Directory",
                "content": "+14155552671",
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.get.side_effect = [resp_429, resp_200]

    with patch("backend.app.engines.discovery.providers.searxng.validate_url_safe"):
        with patch("httpx.AsyncClient", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client), __aexit__=AsyncMock())):
            provider = SearXNGProvider()
            res = await provider.search(valid_phone)
            # Should have fallen back and succeeded on second instance
            assert len(res) == 1
            assert res.outcome.status == ProviderStatus.HEALTHY
            assert res[0].url == "https://example.com/listing"
