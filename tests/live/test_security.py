"""Security controls the app actually has, against the deployed
environment: the headers every response carries, the refusals an anonymous
client gets, and what the responses do not give away.

    BASE_URL=https://localhost:18443 REQUESTS_CA_BUNDLE=ca.crt pytest tests/live/test_security.py

What is *not* here, deliberately: this app has no accounts, no sessions, no
CSRF tokens, no per-object ownership and no database, so there is nothing
to test for IDOR, login redirects, user enumeration or injection into a
query — django-gates-demo's suite tests those because that app has them.
Inventing equivalents here would ship checks that can only fail.
"""

import re

from .client import (
    SECURITY_HEADERS,
    assert_security_headers,
    call,
    create,
    get,
    notes,
    post_json,
    unique,
)


def test_headers_on_the_page():
    """A05 (security misconfiguration): the document response, which is the
    one browsers apply the CSP to."""
    _, headers, _ = get("/")
    assert_security_headers(headers, "the index page")


def test_headers_on_the_api():
    _, headers, _ = get("/api/notes")
    assert_security_headers(headers, "the listing")


def test_headers_on_every_refusal():
    """A05: an error path that skipped the after_request hook would leak the
    missing headers exactly where a scanner looks."""
    refusals = [get("/no-such-path"), get("/api/notes/1"), call("DELETE", "/api/notes"), post_json("/api/notes", {"text": ""})]
    for expected, (status, headers, _) in zip((404, 404, 405, 400), refusals):
        assert status == expected
        assert_security_headers(headers, f"a {status} response")


def test_the_csp_forbids_framing_and_scripts():
    """A05: the two directives that matter most for a page served next to
    whatever else the cluster hosts."""
    _, headers, _ = get("/")
    csp = headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp and "default-src 'none'" in csp and "form-action 'none'" in csp


def test_no_server_version_is_disclosed():
    """A05: a version banner turns a generic finding into a targeted one.
    The Server header names the server, never a build of it."""
    for path in ("/", "/healthz", "/no-such-path"):
        _, headers, _ = get(path)
        server = headers.get("server", "")
        assert not re.search(r"\d", server), f"{path}: Server discloses a version: {server!r}"


def test_unknown_path_is_refused():
    assert get("/no-such-path")[0] == 404
    assert get("/api/nope")[0] == 404


def test_unknown_note_id_is_refused():
    """There is no GET or DELETE on an individual note; the collection is
    the whole surface, so anything under it is a 404 or a 405 — never a
    partial implementation that leaks the shape of stored data."""
    for method in ("GET", "DELETE", "PUT"):
        assert call(method, "/api/notes/1")[0] in (404, 405), f"{method} /api/notes/1 was allowed"


def test_wrong_methods_are_refused():
    assert call("DELETE", "/api/notes")[0] == 405
    assert call("PUT", "/api/notes")[0] == 405
    assert call("POST", "/healthz")[0] == 405


def test_malformed_payloads_are_refused():
    """A03 (injection) at the only boundary the app has: the request body.
    A body that is not the documented object is a 400, never a 500."""
    for body in (None, [], {}, {"text": ""}, {"text": "   "}, {"text": 5}, {"text": ["a"]}, {"text": {"a": 1}}):
        status, _, _ = post_json("/api/notes", body)
        assert status == 400, f"{body!r} was answered {status}"
    assert call("POST", "/api/notes", raw="not json")[0] == 400
    assert call("POST", "/api/notes", raw="[1, 2, 3]")[0] == 400


def test_oversized_text_is_refused():
    """A04 (insecure design): the documented 500-character bound holds."""
    assert post_json("/api/notes", {"text": "x" * 501})[0] == 400
    assert post_json("/api/notes", {"text": "x" * 500})[0] == 201


def test_oversized_text_is_not_stored():
    too_long = unique("nope") + "x" * 501
    assert post_json("/api/notes", {"text": too_long})[0] == 400
    assert all(note["text"] != too_long for note in notes())


def test_user_input_is_returned_as_data_not_markup():
    """A03: the note text is echoed as JSON, and the page never renders a
    note — so markup in a note stays data."""
    payload = "<script>alert(1)</script>"
    note = create(payload)
    assert note["text"] == payload
    _, headers, raw = get("/api/notes")
    assert headers["content-type"].startswith("application/json")
    assert payload.encode() in raw, "the note is not returned verbatim as JSON data"
    _, _, page = get("/")
    assert b"<script>alert(1)" not in page, "a note reached the HTML page"


def test_no_credential_is_issued_or_required():
    """A07 (authentication): the app is anonymous by design and sets no
    cookie at all, so there is no session for a scanner to fixate."""
    for path in ("/", "/healthz", "/api/notes", "/no-such-path"):
        _, headers, _ = get(path)
        assert "set-cookie" not in headers, f"{path} set a cookie: {headers.get('set-cookie')!r}"


def test_the_data_endpoints_are_json():
    """A03: the values the app returns are JSON — never a document, so a
    stored string can't become markup in a browser. (Error pages are
    Flask's own small HTML 404/405 page, which carries the headers above.)"""
    for path in ("/healthz", "/api/notes"):
        _, headers, _ = get(path)
        assert headers.get("content-type", "").startswith("application/json")


def test_every_header_is_present_on_the_health_probe():
    """The probe is the one response the cluster and the health watch read:
    it must carry the same headers as the rest."""
    _, headers, _ = get("/healthz")
    assert set(SECURITY_HEADERS) <= set(headers)
