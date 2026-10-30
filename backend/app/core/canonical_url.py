"""Centralized Canonical URL utility for NumberShield / ClearNum.
Provides safe, RFC-compliant canonicalization of HTTP/HTTPS URLs.

Invariants:
- Normalizes URL scheme and hostname casing to lowercase.
- Removes URL fragment anchors.
- Strips known advertising and analytics tracking parameters (utm_*, fbclid, gclid, etc.).
- Normalizes default network ports (:80 for HTTP, :443 for HTTPS).
- Handles trailing slashes consistently without mutating meaningful resource paths.
- Preserves meaningful query parameters and sorts them deterministically.
- Safely decodes and re-encodes query values to maintain valid encoding.
- Safely rejects malformed or unsupported (non-http/https) URLs.
- Never merges URLs across different hostnames or distinct resource paths.
"""

from typing import Optional, Set
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


# Universal set of known advertising, click tracking, and analytics query parameter keys
TRACKING_PARAM_NAMES: Set[str] = {
    # Meta / Facebook
    "fbclid",
    # Google Ads & Analytics
    "gclid",
    "gclsrc",
    "dclid",
    "wbraid",
    "gbraid",
    "_ga",
    "_gl",
    # Microsoft / Bing Ads
    "msclkid",
    # Yandex
    "yclid",
    "_openstat",
    # Twitter / X
    "twclid",
    # Instagram & TikTok
    "igshid",
    "ttclid",
    # Mailchimp & Email Marketing
    "mc_cid",
    "mc_eid",
    # HubSpot
    "_hsenc",
    "_hsmi",
    "hsctatracking",
    # Miscellaneous Ad / Attribution Networks
    "rb_clickid",
    "wickedid",
    "s_kwcid",
    "ref_src",
    "ref_url",
}


def is_tracking_param(key: str) -> bool:
    """Returns True if the query parameter key is a known tracking or analytics parameter."""
    k_lower = key.strip().lower()
    if k_lower.startswith("utm_"):
        return True
    return k_lower in TRACKING_PARAM_NAMES


def canonicalize_url(url: Optional[str]) -> Optional[str]:
    """Returns a deterministic, normalized canonical representation of an HTTP/HTTPS URL,
    or None if the URL is malformed, unsupported, or empty.

    Ensures that different representations of the same resource (e.g. with differing tracking
    parameters, fragments, casing, or default ports) produce an identical canonical string,
    while distinct paths, hosts, and meaningful query parameters remain strictly separate.
    """
    if not url or not isinstance(url, str):
        return None

    url_str = url.strip()
    if not url_str:
        return None

    try:
        parts = urlsplit(url_str)
    except Exception:
        return None

    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        return None

    if not parts.netloc:
        return None

    try:
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        # Invalid host or port format (e.g. malformed IPv6 or port out of range)
        return None

    if not hostname:
        return None

    hostname = hostname.lower()

    # Reconstruct netloc with default port omitted
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        netloc = hostname
    elif port is not None:
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    # Handle userinfo if present
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo = f"{userinfo}:{parts.password}"
        netloc = f"{userinfo}@{netloc}"

    # Path normalization:
    path = parts.path or ""
    if path:
        # Collapse multiple consecutive slashes
        path = re.sub(r"/+", "/", path)
        # Consistent trailing slash: strip trailing slash for non-root paths; empty for root
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        elif path == "/":
            path = ""

    # Query parameters normalization:
    query = parts.query or ""
    clean_query = ""
    if query:
        try:
            q_pairs = parse_qsl(query, keep_blank_values=True)
            kept_pairs = [
                (k, v) for k, v in q_pairs
                if not is_tracking_param(k)
            ]
            if kept_pairs:
                # Deterministic alphabetical ordering by key, then value
                kept_pairs.sort(key=lambda pair: (pair[0], pair[1]))
                clean_query = urlencode(kept_pairs, doseq=True)
        except Exception:
            clean_query = ""

    # Fragments are strictly omitted
    return urlunsplit((scheme, netloc, path, clean_query, ""))

