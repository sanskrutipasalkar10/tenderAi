"""Guardrail for fetching hyperlinks found inside an uploaded tender PDF
(docs/DECISIONS.md — GeM cover sheets point out to the real tender content instead of
embedding it, e.g. "TERMS AND CONDITIONS ... AS PER ANNEXURE A ENCLOSED" where Annexure
A is a link, not an attachment).

A URL extracted from an uploaded PDF is untrusted input, exactly like the PDF's own
text (CLAUDE.md hard rule 6) — the risk here is network-fetch-injection rather than
prompt-injection: a malicious/malformed tender could embed a link to an internal
service (cloud metadata endpoint, localhost admin panel, internal DB port) and this
pipeline would otherwise fetch it server-side without ever asking whether it should.
No existing module in this codebase does outbound fetches of untrusted-derived URLs —
every prior external call target is this project's own configured infra (S3/Redis/
Postgres) or a single trusted Ollama endpoint — so there was no existing allowlist
pattern to reuse; this is new, not an oversight elsewhere.

Two layers, both required:
  1. Scheme + host-suffix allowlist (app.core.config's linked_doc_allowed_host_suffixes)
     — cheap, first line of defense.
  2. DNS-resolved IP rejection for private/loopback/link-local ranges — defense in
     depth against a DNS-rebinding-style bypass of a pure hostname string check (an
     allowlisted hostname could still resolve to an internal address).
"""

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _host_is_allowlisted(hostname: str) -> bool:
    hostname = hostname.lower()
    return any(
        hostname == suffix or hostname.endswith(f".{suffix}")
        for suffix in settings.linked_doc_allowed_host_suffixes_list
    )


def _resolves_to_private_address(hostname: str) -> bool:
    """Best-effort SSRF defense in depth — if resolution fails outright, treat that as
    unfetchable too (fail closed, never fail open on a DNS error)."""
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except OSError:
        return True

    for _family, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def is_fetchable_url(url: str) -> bool:
    """True only for an https URL whose host is on the allowlist and does not resolve
    to a private/loopback/link-local/reserved address. Never raises — an unparseable
    or unresolvable URL is simply not fetchable, logged, never a pipeline failure.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        logger.warning("link_checks.unparseable_url", url=url)
        return False

    if parsed.scheme != "https":
        logger.warning("link_checks.rejected_non_https", url=url, scheme=parsed.scheme)
        return False

    hostname = parsed.hostname
    if not hostname or not _host_is_allowlisted(hostname):
        logger.warning("link_checks.rejected_host_not_allowlisted", url=url, hostname=hostname)
        return False

    if _resolves_to_private_address(hostname):
        logger.warning("link_checks.rejected_private_address", url=url, hostname=hostname)
        return False

    return True
