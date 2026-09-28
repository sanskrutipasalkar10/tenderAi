"""app.guardrails.link_checks.is_fetchable_url — the SSRF-defense gate every
hyperlink extracted from an uploaded (untrusted) tender PDF must pass before this
pipeline ever fetches it (docs/DECISIONS.md, CLAUDE.md hard rule 6 generalized from
prompt-injection to network-fetch-injection). No real DNS/network calls — hostname
resolution is monkeypatched, per CLAUDE.md hard rule 8.
"""

import socket

import pytest

from app.core.config import settings
from app.guardrails import link_checks


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    """Default: every hostname resolves to a real, public-looking address — individual
    tests override this to simulate a private/loopback/unresolvable target."""
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))]
    )
    monkeypatch.setattr(settings, "linked_doc_allowed_host_suffixes", "gem.gov.in")


def test_accepts_an_allowlisted_https_host() -> None:
    assert link_checks.is_fetchable_url(
        "https://bidplus.gem.gov.in/resources/upload_nas/JulQ325/bidding/biddoc/bid-8051120/1751693557.pdf"
    )


def test_accepts_a_subdomain_of_an_allowlisted_suffix() -> None:
    assert link_checks.is_fetchable_url("https://admin.gem.gov.in/apis/v1/gtc/pdfByDate/")


def test_rejects_non_https_scheme() -> None:
    assert not link_checks.is_fetchable_url("http://bidplus.gem.gov.in/bidding/bid/bidsla/1")


def test_rejects_a_non_allowlisted_host() -> None:
    assert not link_checks.is_fetchable_url("https://evil.example.com/payload.pdf")


def test_rejects_a_lookalike_host_not_matching_the_suffix_boundary() -> None:
    # "notgem.gov.in" must NOT match the "gem.gov.in" suffix just because it ends with
    # the same characters — the check requires a dot boundary, not a raw string suffix.
    assert not link_checks.is_fetchable_url("https://notgem.gov.in/malicious.pdf")


def test_rejects_unparseable_url() -> None:
    assert not link_checks.is_fetchable_url("not a url at all")


def test_rejects_hostname_resolving_to_a_loopback_address(monkeypatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda host, port: [(2, 1, 6, "", ("127.0.0.1", 0))]
    )
    assert not link_checks.is_fetchable_url("https://bidplus.gem.gov.in/x.pdf")


def test_rejects_hostname_resolving_to_a_link_local_metadata_address(monkeypatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda host, port: [(2, 1, 6, "", ("169.254.169.254", 0))]
    )
    assert not link_checks.is_fetchable_url("https://bidplus.gem.gov.in/x.pdf")


def test_rejects_hostname_resolving_to_a_private_range_address(monkeypatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda host, port: [(2, 1, 6, "", ("10.0.0.5", 0))]
    )
    assert not link_checks.is_fetchable_url("https://bidplus.gem.gov.in/x.pdf")


def test_fails_closed_when_dns_resolution_raises(monkeypatch) -> None:
    def _raise(host, port):
        raise OSError("DNS resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", _raise)
    assert not link_checks.is_fetchable_url("https://bidplus.gem.gov.in/x.pdf")
