"""Server-Side Request Forgery (SSRF) protection and safe HTTP client.
Ensures external requests cannot target private network interfaces, loopbacks,
AWS/GCP/Azure cloud metadata services (169.254.169.254), or local daemons.

Enforces connection pinning at the socket layer to eliminate DNS rebinding TOCTOU gaps,
revalidates redirect destinations, checks Content-Type, and bounds response sizes.
"""

import ipaddress
import socket
from urllib.parse import urlparse
import httpx
import httpcore
from httpcore._backends.anyio import AnyIOBackend
from backend.app.core.config import settings

# Disallowed private, loopback, link-local, multicast, carrier-grade NAT, and cloud metadata subnets
DISALLOWED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network (RFC 1122)
    ipaddress.ip_network("10.0.0.0/8"),         # Private Class A (RFC 1918)
    ipaddress.ip_network("100.64.0.0/10"),      # Shared Address Space / CGNAT (RFC 6598)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback IPv4 (RFC 1122)
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local & Cloud Metadata 169.254.169.254 (RFC 3927)
    ipaddress.ip_network("172.16.0.0/12"),      # Private Class B (RFC 1918)
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments (RFC 6890)
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1 (RFC 5737)
    ipaddress.ip_network("192.88.99.0/24"),     # 6to4 Relay Anycast (RFC 7526)
    ipaddress.ip_network("192.168.0.0/16"),     # Private Class C (RFC 1918)
    ipaddress.ip_network("198.18.0.0/15"),      # Network Interconnect Benchmarking (RFC 2544)
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2 (RFC 5737)
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3 (RFC 5737)
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast (RFC 5771)
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved (RFC 1112)
    ipaddress.ip_network("255.255.255.255/32"), # Limited Broadcast (RFC 919)
]

DISALLOWED_IPV6_NETWORKS = [
    ipaddress.ip_network("::/128"),             # Unspecified address (RFC 4291)
    ipaddress.ip_network("::1/128"),            # Loopback IPv6 (RFC 4291)
    ipaddress.ip_network("::ffff:0:0/96"),      # IPv4-mapped IPv6 (RFC 4291)
    ipaddress.ip_network("64:ff9b::/96"),       # IPv4/IPv6 translation (RFC 6052)
    ipaddress.ip_network("100::/64"),           # Discard prefix (RFC 6666)
    ipaddress.ip_network("2001:db8::/32"),      # Documentation (RFC 3849)
    ipaddress.ip_network("fc00::/7"),           # Unique Local Address ULA (RFC 4193)
    ipaddress.ip_network("fe80::/10"),          # Link-local unicast (RFC 4291)
    ipaddress.ip_network("ff00::/8"),           # Multicast (RFC 4291)
]

DISALLOWED_NETWORKS = DISALLOWED_IPV4_NETWORKS + DISALLOWED_IPV6_NETWORKS

BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "instance-data",
    "metadata.nic.internal",
}

PERMITTED_CONTENT_TYPES = (
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
    "application/json",
)


class SSRFValidationError(Exception):
    """Raised when a URL targets a disallowed or private network address."""
    pass


def is_ip_allowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> tuple[bool, str]:
    """Inspects an IP address against forbidden network specifications."""
    if ip.is_loopback:
        return False, f"Loopback address '{ip}'"
    if ip.is_private:
        return False, f"Private address '{ip}'"
    if ip.is_link_local:
        return False, f"Link-local address '{ip}'"
    if ip.is_multicast:
        return False, f"Multicast address '{ip}'"
    if ip.is_reserved:
        return False, f"Reserved address '{ip}'"
    if ip.is_unspecified:
        return False, f"Unspecified address '{ip}'"

    # Handle IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        mapped_v4 = ip.ipv4_mapped
        for net in DISALLOWED_IPV4_NETWORKS:
            if mapped_v4 in net:
                return False, f"IPv4-mapped address '{ip}' targets disallowed IPv4 range '{net}'"

    # Check explicit network lists
    if isinstance(ip, ipaddress.IPv4Address):
        for net in DISALLOWED_IPV4_NETWORKS:
            if ip in net:
                return False, f"IPv4 address '{ip}' in disallowed subnet '{net}'"
    elif isinstance(ip, ipaddress.IPv6Address):
        for net in DISALLOWED_IPV6_NETWORKS:
            if ip in net:
                return False, f"IPv6 address '{ip}' in disallowed subnet '{net}'"

    return True, ""


def resolve_and_validate_host(hostname: str, port: int = 80) -> list[str]:
    """Resolves DNS for a hostname and verifies every resolved IPv4 and IPv6 record.
    Returns the list of validated IP strings or raises SSRFValidationError.
    """
    clean_host = hostname.strip().lower().strip("[]")
    if not clean_host:
        raise SSRFValidationError("Hostname cannot be empty")

    if clean_host in BLOCKED_HOSTNAMES:
        raise SSRFValidationError(f"Access to '{hostname}' is blocked for SSRF prevention.")

    # Check for direct integer/hex/decimal IP bypasses
    if clean_host.isdigit():
        try:
            int_ip = ipaddress.ip_address(int(clean_host))
            allowed, reason = is_ip_allowed(int_ip)
            if not allowed:
                raise SSRFValidationError(f"Target '{hostname}' resolves to blocked IP: {reason}")
            return [str(int_ip)]
        except ValueError:
            pass

    # Check if host is already a direct IP address
    try:
        direct_ip = ipaddress.ip_address(clean_host)
        allowed, reason = is_ip_allowed(direct_ip)
        if not allowed:
            raise SSRFValidationError(f"Target '{hostname}' is a blocked address: {reason}")
        return [str(direct_ip)]
    except ValueError:
        pass  # Hostname is a domain name, proceed with DNS resolution

    try:
        addr_info = socket.getaddrinfo(clean_host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise SSRFValidationError(f"DNS resolution failed for hostname '{hostname}': {e}")

    if not addr_info:
        raise SSRFValidationError(f"Could not resolve any IP addresses for '{hostname}'")

    validated_ips = []
    for _, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFValidationError(f"Invalid resolved IP '{ip_str}'")

        allowed, reason = is_ip_allowed(ip_obj)
        if not allowed:
            raise SSRFValidationError(
                f"Target hostname '{hostname}' resolved to blocked IP '{ip_str}': {reason}"
            )
        if ip_str not in validated_ips:
            validated_ips.append(ip_str)

    if not validated_ips:
        raise SSRFValidationError(f"No valid public destination addresses found for '{hostname}'")

    return validated_ips


class SSRFSafeNetworkBackend(AnyIOBackend):
    """Network backend that intercepts TCP socket connections, re-verifies destination IPs,
    and pins the socket connection directly to the validated IP to defeat DNS rebinding.
    """

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        validated_ips = resolve_and_validate_host(host, port)
        chosen_ip = validated_ips[0]
        # Connect directly to the validated IP, bypassing any second DNS resolution
        return await super().connect_tcp(
            host=chosen_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class SSRFSafeTransport(httpx.AsyncHTTPTransport):
    """Custom AsyncHTTPTransport utilizing SSRFSafeNetworkBackend and disabled keepalive
    to ensure fresh socket validation and eliminate DNS rebinding TOCTOU windows.
    """

    def __init__(self, *args, **kwargs):
        # Force trust_env to False to prevent proxy environment bypasses
        kwargs["trust_env"] = False
        super().__init__(*args, **kwargs)
        # Reinitialize the connection pool with our pinned SSRFSafeNetworkBackend
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            max_connections=self._pool._max_connections,
            max_keepalive_connections=0,  # Disable connection reuse across distinct requests
            keepalive_expiry=0.0,
            http1=self._pool._http1,
            http2=self._pool._http2,
            retries=0,
            local_address=self._pool._local_address,
            uds=self._pool._uds,
            network_backend=SSRFSafeNetworkBackend(),
            socket_options=self._pool._socket_options,
        )


def validate_url_safe(url: str) -> str:
    """Validates that a URL uses http/https, has a valid hostname, and resolves
    strictly to permitted public network addresses.
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

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    resolve_and_validate_host(hostname, port)
    return url.strip()


async def safe_fetch_url(
    url: str,
    timeout: float = settings.request_timeout,
    max_size: int = settings.max_response_size,
    max_redirects: int = 5,
) -> tuple[int, str, dict]:
    """Safely fetches a web page content while enforcing SSRF checks, socket connection pinning,
    timeouts, response size limits, content-type whitelisting, and redirect revalidation.
    Returns: (status_code, text_content, headers)
    """
    current_url = validate_url_safe(url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36 (NumberShield Privacy Bot/1.0)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
    }

    client_timeout = httpx.Timeout(
        timeout,
        connect=min(timeout, 5.0),
        read=timeout,
        write=timeout,
        pool=timeout,
    )
    transport = SSRFSafeTransport(verify=True)

    redirect_count = 0
    async with httpx.AsyncClient(
        transport=transport,
        timeout=client_timeout,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        while redirect_count <= max_redirects:
            try:
                # Stream response to inspect headers and enforce size limit safely
                async with client.stream("GET", current_url, headers=headers) as response:
                    # Check for redirect status codes
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location:
                            raise SSRFValidationError("Redirect response missing Location header")
                        next_url = str(httpx.URL(current_url).join(location))
                        # Re-validate destination URL
                        current_url = validate_url_safe(next_url)
                        redirect_count += 1
                        if redirect_count > max_redirects:
                            raise SSRFValidationError("Too many redirects (exceeded limit of 5)")
                        continue

                    # Validate Content-Type header
                    raw_content_type = response.headers.get("content-type", "")
                    content_type = raw_content_type.split(";")[0].strip().lower()
                    if content_type and not any(content_type == perm for perm in PERMITTED_CONTENT_TYPES):
                        raise SSRFValidationError(
                            f"Disallowed content type '{content_type}'. Only HTML, XML, JSON, and text responses are permitted."
                        )

                    # Validate declared Content-Length
                    content_length = response.headers.get("content-length")
                    if content_length and content_length.isdigit() and int(content_length) > max_size:
                        raise SSRFValidationError(
                            f"Response size {content_length} bytes exceeds maximum limit {max_size} bytes"
                        )

                    # Stream content with hard byte cap
                    body_chunks = []
                    total_bytes = 0
                    async for chunk in response.aiter_bytes():
                        total_bytes += len(chunk)
                        if total_bytes > max_size:
                            raise SSRFValidationError(
                                f"Response stream exceeded maximum limit of {max_size} bytes"
                            )
                        body_chunks.append(chunk)

                    content = b"".join(body_chunks).decode("utf-8", errors="replace")
                    return response.status_code, content, dict(response.headers)

            except httpx.RequestError as exc:
                raise SSRFValidationError(f"HTTP request error: {exc}")

        raise SSRFValidationError("Too many redirects")
