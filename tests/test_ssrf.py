"""Tests for Server-Side Request Forgery (SSRF) defenses."""

import pytest
from backend.app.core.ssrf import validate_url_safe, SSRFValidationError


@pytest.mark.parametrize("dangerous_url", [
    "http://127.0.0.1",
    "http://127.0.0.1:8000/admin",
    "http://localhost:5000",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.1/internal",
    "http://192.168.1.1/router",
    "http://172.16.0.1/status",
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_ping",
    "ftp://ftp.example.com",
    "",
])
def test_ssrf_rejects_disallowed_addresses(dangerous_url):
    with pytest.raises(SSRFValidationError):
        validate_url_safe(dangerous_url)


def test_ssrf_allows_public_web_urls():
    # Valid external public hostname
    valid_url = "https://example.com"
    result = validate_url_safe(valid_url)
    assert result == valid_url
