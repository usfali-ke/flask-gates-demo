"""Integration: the deployed app with its real parts together — the
environment's TLS ingress in front of the gunicorn worker, the JSON API and
the HTML page, through one connection, with the app's own validation.

    BASE_URL=https://localhost:18443 REQUESTS_CA_BUNDLE=ca.crt pytest tests/live/test_integration.py

Notes live in the single gunicorn worker's memory (the Dockerfile pins one
worker) and the dev/staging controls run in parallel against the same pod,
so these tests assert what one client can see of its own writes — never a
global count or an id sequence, which other jobs' notes would break.
"""

from urllib.parse import urlsplit

import pytest

from .client import (
    BASE,
    assert_security_headers,
    body_json,
    call,
    create,
    get,
    notes,
    post_json,
    unique,
)


def test_https_ingress_serves_the_app():
    """The suite reaches the app through the ingress: a certificate that
    verifies against the environment's CA (REQUESTS_CA_BUNDLE) and the
    app's own JSON health answer."""
    if urlsplit(BASE).scheme != "https":
        pytest.skip("BASE_URL is not HTTPS (the release's env-up.sh always is)")
    status, headers, raw = get("/healthz")
    assert status == 200 and body_json(raw) == {"status": "ok"}
    assert_security_headers(headers, "/healthz over TLS")


def test_page_and_api_are_the_same_process():
    """A note written through the API is visible to the next request: one
    worker, no session, no database to be out of step with."""
    note = create(unique("integration"))
    assert isinstance(note["id"], int) and note["id"] >= 1
    assert note in notes()


def test_validation_through_the_ingress():
    """The app's own 400s reach the client through the proxy — not a 502
    from the ingress, and not a stored note."""
    invalid = [None, {}, {"text": ""}, {"text": "   "}, {"text": 5}, {"text": "x" * 501}, {"text": ["a"]}]
    for body in invalid:
        status, _, raw = post_json("/api/notes", body)
        assert status == 400, f"{body!r} was answered {status}: {raw!r}"
    status, _, _ = call("POST", "/api/notes", raw="not json")
    assert status == 400


def test_oversized_text_is_not_stored():
    too_long = unique("overlong") + "x" * 501
    assert post_json("/api/notes", {"text": too_long})[0] == 400
    assert all(note["text"] != too_long for note in notes())


def test_page_is_html_and_api_is_json():
    status, headers, _ = get("/")
    assert status == 200 and headers["content-type"].startswith("text/html")
    status, headers, _ = get("/api/notes")
    assert status == 200 and headers["content-type"].startswith("application/json")
