# NumberShield SSRF Security Architecture & Threat Model

## 1. Overview & Security Objectives

NumberShield enables users to safely verify online exposures of their own phone numbers by fetching live web pages (e.g. data broker listings, paste sites, or custom verification targets). Because arbitrary external URLs can be supplied or discovered, the HTTP client must be strictly prevented from serving as a proxy or pivot into internal infrastructure, loopback daemons, link-local interfaces, or cloud metadata endpoints.

---

## 2. Threat Model & Scenarios Covered

| Attack Vector | Threat Description | Defense Mechanism in `backend/app/core/ssrf.py` |
| :--- | :--- | :--- |
| **DNS Rebinding (TOCTOU)** | Attacker configures domain with TTL=0 returning public IP on pre-validation check, but returning `127.0.0.1` on socket connection. | **Socket-level IP Connection Pinning**: `SSRFSafeNetworkBackend.connect_tcp` intercepts the connection at the socket layer, resolves DNS, validates all resolved IPs, and directly passes the pre-validated IP string (`remote_host=chosen_ip`) to `anyio.connect_tcp`. Zero second DNS resolution occurs. |
| **IPv4-Mapped IPv6** | Attacker specifies `[::ffff:127.0.0.1]` or `[::ffff:169.254.169.254]` to bypass IPv4 subnet string filters. | **Dual-Layer IPv6 Mapping Inspection**: Any IPv6 address with `ip.ipv4_mapped` extracts the mapped IPv4 address and verifies it against the entire IPv4 disallowed block (`127.0.0.0/8`, `169.254.0.0/16`, RFC 1918). The entire `::ffff:0:0/96` block is also blocked by default. |
| **Mixed DNS Record Poisoning** | DNS returns a round-robin of both public (`93.184.216.34`) and private (`10.0.0.1`) addresses. | **Universal Address Validation**: `resolve_and_validate_host()` iterates through every resolved A and AAAA record. If *any* record falls in a disallowed subnet, the entire host is rejected with `SSRFValidationError`. |
| **Cloud Metadata Harvesting** | Attacker targets AWS/GCP/Azure/DigitalOcean metadata IP `169.254.169.254` or hostnames (`metadata.google.internal`, `instance-data`). | Blocked at both hostname level (`BLOCKED_HOSTNAMES`) and CIDR level (`169.254.0.0/16` link-local subnet). |
| **Decimal / Integer / Octal IP Bypass** | Attacker uses `http://2130706433/` (`127.0.0.1` in decimal notation). | `resolve_and_validate_host()` parses numeric string hostnames as integer IP representations and rejects disallowed subnets. |
| **Redirect to Internal Resources** | Public hop (`https://example.com`) returns HTTP 302 redirecting to `http://127.0.0.1/admin`. | **Hop-by-hop Revalidation**: `safe_fetch_url` sets `follow_redirects=False`. Every redirect hop (301, 302, 303, 307, 308) computes the absolute destination URL and re-runs `validate_url_safe()`, plus socket-level pinning on the subsequent request. Max 5 hops enforced. |
| **Denial of Service / Gigabyte Bombs** | Target returns an infinite stream or multi-gigabyte file to exhaust memory. | **Streaming Chunk Limiting**: Responses are streamed with `response.aiter_bytes()`. If total bytes received exceed `max_response_size` (default 5MB), streaming is immediately aborted and raises `SSRFValidationError`. |
| **Executable / Binary MIME Attacks** | Target serves binary executables, archives, or malware. | **Content-Type Whitelist**: Responses must declare or match `text/html`, `text/plain`, `application/xhtml+xml`, `application/xml`, `text/xml`, or `application/json`. Disallowed MIME types (e.g. `application/octet-stream`) abort immediately. |
| **Environment Proxy Bypass** | System has `HTTP_PROXY` or `HTTPS_PROXY` configured which would forward requests to an unvalidated intermediary. | **`trust_env=False`**: Client and transport strictly ignore environment proxy variables. |

---

## 3. Implementation Architecture & Trade-Offs

### Socket-Level IP Pinning with SNI and Host Preservation
- **Challenge**: Standard HTTP clients that allow setting an IP destination (like `curl --resolve`) often break TLS certificate verification and SNI headers if not carefully coordinated.
- **Solution**: We subclass `AnyIOBackend` to intercept `connect_tcp(host, port)`. When `connect_tcp` executes, it resolves DNS, checks all addresses against `DISALLOWED_NETWORKS`, and passes the validated IP address to `anyio.connect_tcp(remote_host=chosen_ip, ...)`. Because the TCP stream is now connected to that specific IP, no further DNS resolution can take place.
- When `httpcore` initiates TLS handshake via `stream.start_tls()`, it uses `server_hostname=sni_hostname or self._origin.host.decode("ascii")`, preserving the original domain name in SNI and ensuring proper X.509 certificate hostname verification.
- HTTP `Host` headers remain identical to the requested domain.

### Trade-Offs
1. **Connection Keep-Alive Disabled (`keepalive_expiry=0.0`)**:
   - *Rationale*: Reusing TCP sockets across different requests could allow a connection originally opened to a valid IP to be reused if DNS rebinding occurred between sessions, or could bypass per-request validation.
   - *Trade-off*: Disabling keep-alive adds ~20-50ms TCP/TLS handshake latency for repeated requests to the same host. For a privacy audit scanner that fetches individual broker pages, this small latency is well worth the cryptographic and SSRF isolation.
2. **Strict MIME Filtering**:
   - *Rationale*: Protects downstream DOM parsers and scrapers from unexpected binary payloads.
   - *Trade-off*: Misconfigured servers that serve HTML as `application/octet-stream` will be rejected.

---

## 4. Remaining Limitations

1. **Egress to Permitted Public Services**:
   - SSRF protection prevents access to private and metadata networks. However, outbound HTTP requests to valid public websites will originate from the user's IP (or active VPN). Users seeking anonymity against target sites should use Tor or an external VPN.
2. **DNS Resolution Latency**:
   - Strict resolution of both IPv4 and IPv6 addresses requires operating system resolver support. If local DNS is experiencing high packet loss, `socket.gaierror` will be raised and treated as unreachable.
