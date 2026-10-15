"""Post-deployment smoke tests: read-only — GETs only, no writes — so they
are safe against prod (the release runs them right after prod's rollout;
dev's and staging's suites run them too).

    BASE_URL=https://localhost:18443 REQUESTS_CA_BUNDLE=ca.crt pytest tests/live/test_smoke.py

Selected by file, not by a pytest marker: the repo's pyproject.toml
registers no markers (it is outside this change), and an unregistered
`-m smoke` filter would only warn.
"""

import os
from urllib.parse import urlsplit

import pytest

from .client import BASE, assert_security_headers, body_json, call, call_absolute, get


def test_healthz():
    """The probe the Rollout, the Dockerfile HEALTHCHECK and the health watch
    all use: 200, exactly {"status": "ok"}, and not cached."""
    status, headers, raw = get("/healthz")
    assert status == 200
    assert body_json(raw) == {"status": "ok"}
    assert headers.get("content-type", "").startswith("application/json")
    assert headers.get("cache-control") == "no-store"


def test_index_page_renders():
    status, headers, raw = get("/")
    assert status == 200
    assert headers.get("content-type", "").startswith("text/html")
    assert b"flask-gates-demo" in raw


def test_listing_notes_is_readable():
    status, _, raw = get("/api/notes")
    assert status == 200
    assert isinstance(body_json(raw).get("notes"), list)


def test_unknown_path_is_refused():
    status, headers, _ = get("/no-such-path")
    assert status == 404
    assert_security_headers(headers, "404")


def test_method_not_allowed():
    """The collection takes GET and POST; there is no way to delete
    everything, and the app says so rather than 404ing."""
    status, _, _ = call("DELETE", "/api/notes")
    assert status == 405


def test_security_headers_on_every_response():
    for path in ("/", "/healthz", "/api/notes", "/no-such-path"):
        status, headers, _ = get(path)
        assert status in (200, 404)
        assert_security_headers(headers, path)


def test_plain_http_redirects_to_https():
    """The ingress (tests/env/Caddyfile) serves the app over TLS and sends
    plain http to it, the way a user typing the address would be."""
    parts = urlsplit(BASE)
    if parts.scheme != "https":
        pytest.skip("BASE_URL is not HTTPS (the release's env-up.sh always is)")
    http_url = os.environ.get("HTTP_URL") or f"http://{parts.hostname}:{parts.port}"
    status, headers = call_absolute(http_url.rstrip("/") + "/healthz")
    assert status in (301, 302, 307, 308), f"http answered {status}, expected a redirect"
    assert headers.get("location", "").startswith("https://")
