"""Server-Side Request Forgery (SSRF) protection and safe HTTP client.
Ensures external requests cannot target private network interfaces, loopbacks,
AWS/cloud metadata services (169.254.169.254), or local daemons.
"""

import socket
import ipaddress
from urllib.parse import urlparse
import httpx
from backend.app.core.config import settings

# Disallowed private, loopback, link-local, multicast, and cloud metadata subnets
DISALLOWED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),          # Loopback IPv4
    ipaddress.ip_network("::1/128"),              # Loopback IPv6
    ipaddress.ip_network("10.0.0.0/8"),           # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),        # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),       # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),       # Link-local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("fe80::/10"),            # IPv6 Link-local
    ipaddress.ip_network("fc00::/7"),             # IPv6 Unique Local
    ipaddress.ip_network("0.0.0.0/8"),            # Current network
    ipaddress.ip_network("224.0.0.0/4"),          # Multicast
    ipaddress.ip_network("240.0.0.0/4"),          # Reserved
]


class SSRFValidationError(Exception):
    """Raised when a URL targets a disallowed or private network address."""
    pass


def validate_url_safe(url: str) -> str:
    """Validates that a URL uses http/https and does not resolve to private/local IPs.
    Returns the validated URL string or raises SSRFValidationError.
    """
    if not url or not isinstance(url, str):
        raise SSRFValidationError("URL cannot be empty")
    
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise SSRFValidationError(f"Invalid scheme '{parsed.scheme}'. Only http and https are permitted.")
    
    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("URL missing hostname")
    
    # Reject explicit localhost strings
    lower_host = hostname.lower()
    if lower_host in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "metadata.google.internal"):
        raise SSRFValidationError(f"Access to '{hostname}' is blocked for SSRF prevention.")
    
    # Resolve hostname to IP addresses and verify every resolved IP
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise SSRFValidationError(f"DNS resolution failed for hostname '{hostname}': {e}")
    
    if not addr_info:
        raise SSRFValidationError(f"Could not resolve any IP addresses for '{hostname}'")
    
    for family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFValidationError(f"Invalid resolved IP '{ip_str}'")
        
        for network in DISALLOWED_NETWORKS:
            if ip_obj in network:
                raise SSRFValidationError(
                    f"Target hostname '{hostname}' resolved to blocked private/local IP '{ip_str}' in '{network}'"
                )
    
    return url.strip()


async def safe_fetch_url(url: str, timeout: float = settings.request_timeout, max_size: int = settings.max_response_size) -> tuple[int, str, dict]:
    """Safely fetches a web page content while enforcing SSRF checks, timeouts,
    size limits, and redirect validation.
    Returns: (status_code, text_content, headers)
    """
    validated_url = validate_url_safe(url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (NumberShield Privacy Bot/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    current_url = validated_url
    max_redirects = 5
    redirect_count = 0
    
    async with httpx.AsyncClient(timeout=timeout, verify=True, follow_redirects=False) as client:
        while redirect_count < max_redirects:
            # Re-validate current URL at every redirect hop
            validate_url_safe(current_url)
            
            try:
                response = await client.get(current_url, headers=headers)
            except httpx.RequestError as exc:
                raise SSRFValidationError(f"HTTP request error: {exc}")
            
            # Check for redirect status codes
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    break
                # Resolve relative redirects
                next_url = str(httpx.URL(current_url).join(location))
                current_url = validate_url_safe(next_url)
                redirect_count += 1
                continue
            
            # Check content length header if provided
            content_length = response.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > max_size:
                raise SSRFValidationError(f"Response size {content_length} bytes exceeds maximum limit {max_size} bytes")
            
            # Read content stream up to max_size
            content = response.text
            if len(content.encode("utf-8", errors="replace")) > max_size:
                content = content[:max_size]
            
            return response.status_code, content, dict(response.headers)
            
        raise SSRFValidationError("Too many redirects")
