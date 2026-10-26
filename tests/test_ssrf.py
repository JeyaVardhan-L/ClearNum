"""Deterministic unit and integration tests for Server-Side Request Forgery (SSRF) defenses."""

import socket
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from backend.app.core.ssrf import (
    validate_url_safe,
    safe_fetch_url,
    resolve_and_validate_host,
    SSRFValidationError,
    SSRFSafeTransport,
    SSRFSafeNetworkBackend,
    is_ip_allowed,
)
import ipaddress


@pytest.mark.parametrize("dangerous_url", [
    "http://127.0.0.1",
    "http://127.0.0.1:8000/admin",
    "http://localhost:5000",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.1/internal",
    "http://192.168.1.1/router",
    "http://172.16.0.1/status",
    "http://100.64.0.1/cgnat",
    "http://0.0.0.0:8000/",
    "http://255.255.255.255/broadcast",
    "http://240.0.0.1/reserved",
    "http://[::1]/",
    "http://[::]/",
    "http://[fe80::1]/",
    "http://[fc00::1]/",
    "http://[::ffff:127.0.0.1]/",
    "http://[::ffff:169.254.169.254]/",
    "http://[::ffff:10.0.0.1]/",
    "http://2130706433/",  # Decimal representation of 127.0.0.1
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://instance-data/latest/meta-data/",
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_ping",
    "ftp://ftp.example.com",
    "",
])
def test_ssrf_rejects_disallowed_addresses_and_schemes(dangerous_url):
    with pytest.raises(SSRFValidationError):
        validate_url_safe(dangerous_url)


def test_ssrf_allows_public_web_urls():
    valid_url = "https://example.com"
    result = validate_url_safe(valid_url)
    assert result == valid_url


def test_ssrf_rejects_mixed_dns_with_private_ip():
    """If a hostname resolves to multiple IPs and even ONE is private, reject it."""
    fake_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.5", 80)),
    ]
    with patch("socket.getaddrinfo", return_value=fake_addr_info):
        with pytest.raises(SSRFValidationError) as exc_info:
            resolve_and_validate_host("mixed.attacker.com", 80)
        assert "disallowed" in str(exc_info.value).lower() or "blocked" in str(exc_info.value).lower()


def test_ssrf_rejects_dns_returning_loopback():
    fake_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80)),
    ]
    with patch("socket.getaddrinfo", return_value=fake_addr_info):
        with pytest.raises(SSRFValidationError) as exc_info:
            resolve_and_validate_host("rebind.attacker.com", 80)
        assert "127.0.0.1" in str(exc_info.value)


def test_ssrf_rejects_dns_returning_cloud_metadata():
    fake_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("169.254.169.254", 80)),
    ]
    with patch("socket.getaddrinfo", return_value=fake_addr_info):
        with pytest.raises(SSRFValidationError) as exc_info:
            resolve_and_validate_host("cloudmeta.attacker.com", 80)
        assert "169.254.169.254" in str(exc_info.value)


def test_is_ip_allowed_ipv4_mapped_ipv6():
    # IPv4-mapped loopback
    ip_mapped_loopback = ipaddress.ip_address("::ffff:127.0.0.1")
    allowed, reason = is_ip_allowed(ip_mapped_loopback)
    assert not allowed
    assert "loopback" in reason.lower() or "mapped" in reason.lower()

    # IPv4-mapped metadata
    ip_mapped_meta = ipaddress.ip_address("::ffff:169.254.169.254")
    allowed, reason = is_ip_allowed(ip_mapped_meta)
    assert not allowed

    # IPv4-mapped public IP
    ip_mapped_public = ipaddress.ip_address("::ffff:93.184.216.34")
    # 93.184.216.34 is public, but ::ffff:0:0/96 is in DISALLOWED_IPV6_NETWORKS to prevent mapping ambiguity
    allowed, reason = is_ip_allowed(ip_mapped_public)
    assert not allowed


@pytest.mark.asyncio
async def test_ssrf_network_backend_pins_connection():
    """Verify that SSRFSafeNetworkBackend resolves DNS, validates it, and passes the IP to super().connect_tcp."""
    backend = SSRFSafeNetworkBackend()
    fake_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
    ]

    with patch("socket.getaddrinfo", return_value=fake_addr_info):
        with patch.object(SSRFSafeNetworkBackend.__bases__[0], "connect_tcp", new_callable=AsyncMock) as mock_super_connect:
            mock_super_connect.return_value = MagicMock()
            await backend.connect_tcp(host="example.com", port=443)
            # Must connect directly to the pinned IP '93.184.216.34', NOT the hostname
            mock_super_connect.assert_called_once()
            call_kwargs = mock_super_connect.call_args.kwargs
            assert call_kwargs["host"] == "93.184.216.34"
            assert call_kwargs["port"] == 443


@pytest.mark.asyncio
async def test_safe_fetch_url_rejects_disallowed_content_type():
    """Safe fetch must abort when Content-Type is not in the permitted whitelist (e.g. binary/executable)."""
    with patch("backend.app.core.ssrf.validate_url_safe", return_value="https://example.com/binary.exe"):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/octet-stream"}

        class FakeStreamContext:
            async def __aenter__(self):
                return mock_response
            async def __aexit__(self, *args):
                pass

        with patch("httpx.AsyncClient.stream", return_value=FakeStreamContext()):
            with pytest.raises(SSRFValidationError) as exc_info:
                await safe_fetch_url("https://example.com/binary.exe")
            assert "content type" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_safe_fetch_url_enforces_max_size_header():
    """Safe fetch must abort when declared Content-Length exceeds maximum limit."""
    with patch("backend.app.core.ssrf.validate_url_safe", return_value="https://example.com/huge.html"):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "text/html",
            "content-length": "100000000",  # 100 MB
        }

        class FakeStreamContext:
            async def __aenter__(self):
                return mock_response
            async def __aexit__(self, *args):
                pass

        with patch("httpx.AsyncClient.stream", return_value=FakeStreamContext()):
            with pytest.raises(SSRFValidationError) as exc_info:
                await safe_fetch_url("https://example.com/huge.html", max_size=1024)
            assert "exceeds maximum limit" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_safe_fetch_url_enforces_streaming_body_limit():
    """Safe fetch must abort when incoming chunked body stream exceeds maximum limit."""
    with patch("backend.app.core.ssrf.validate_url_safe", return_value="https://example.com/stream.html"):
        async def fake_aiter():
            yield b"A" * 600
            yield b"B" * 600

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.aiter_bytes = fake_aiter

        class FakeStreamContext:
            async def __aenter__(self):
                return mock_response
            async def __aexit__(self, *args):
                pass

        with patch("httpx.AsyncClient.stream", return_value=FakeStreamContext()):
            with pytest.raises(SSRFValidationError) as exc_info:
                await safe_fetch_url("https://example.com/stream.html", max_size=1000)
            assert "exceeded maximum limit" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_safe_fetch_url_revalidates_redirect_to_private():
    """If hop 1 redirects to an internal/private address, safe_fetch_url must reject it."""
    with patch("backend.app.core.ssrf.validate_url_safe") as mock_validate:
        # First call allows public URL, second call on the redirect target rejects loopback
        def side_effect(u):
            if "127.0.0.1" in u:
                raise SSRFValidationError("Redirect to loopback blocked")
            return u
        mock_validate.side_effect = side_effect

        mock_redirect_response = MagicMock()
        mock_redirect_response.status_code = 302
        mock_redirect_response.headers = {"Location": "http://127.0.0.1:8000/internal"}

        class FakeStreamContext:
            async def __aenter__(self):
                return mock_redirect_response
            async def __aexit__(self, *args):
                pass

        with patch("httpx.AsyncClient.stream", return_value=FakeStreamContext()):
            with pytest.raises(SSRFValidationError) as exc_info:
                await safe_fetch_url("https://example.com/redirect")
            assert "loopback blocked" in str(exc_info.value)
