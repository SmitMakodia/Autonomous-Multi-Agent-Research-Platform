"""Outbound URL guard (SSRF).

Scrape targets are untrusted from two directions: ``web_scrape_url`` takes a URL chosen by
the LLM, and the search agent scrapes whatever hrefs DuckDuckGo hands back. Without a
check, either can be pointed at the loopback interface (the unauthenticated llama-server
on :8000, or AgentForge's own API), at a LAN host, or at a cloud metadata endpoint — and
the response body is then fed to the model and shown to the user.
"""

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsafeURLError(ValueError):
    """A URL resolved to a non-public address or used a disallowed scheme."""


def _is_blocked(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local  # covers 169.254.169.254 cloud metadata
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_public_url(url: str) -> str:
    """Return ``url`` unchanged, or raise ``UnsafeURLError``.

    Every address the hostname resolves to must be public — checking only the first would
    let a multi-record host slip a private address through.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"scheme not allowed: {parsed.scheme or '(none)'}")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError(f"no host in URL: {url!r}")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"cannot resolve host {host!r}: {exc}") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked(ip):
            raise UnsafeURLError(f"host {host!r} resolves to non-public address {ip}")

    # ponytail: resolve-then-fetch leaves a DNS-rebinding window - the name could map to a
    # private address by the time httpx/Chromium connects. Closing it means pinning the
    # validated IP into the connection, which crawl4ai's Chromium path cannot express.
    # Acceptable for a single-user local tool; revisit if this is ever exposed to others.
    return url
