"""End-to-end: a user's journey through the deployed environment — open the
page, add a note the page documents, see it listed again, all through the
ingress.

    BASE_URL=https://localhost:18443 REQUESTS_CA_BUNDLE=ca.crt pytest tests/live/test_e2e.py

Staging runs this before UAT sign-off; dev runs the integration suite.
Notes are per-pod memory and the controls run in parallel, so the journey
asserts only of its own notes.
"""

from .client import (
    assert_security_headers,
    body_json,
    create,
    get,
    notes,
    post_json,
    unique,
)


def test_a_visitor_can_read_the_page():
    status, headers, page = get("/")
    assert status == 200
    assert headers.get("content-type", "").startswith("text/html")
    assert b"flask-gates-demo" in page
    assert_security_headers(headers, "the index page")


def test_a_visitor_can_add_a_note_and_see_it_listed():
    text = unique("journey")
    note = create(text)
    assert note["text"] == text
    listed = notes()
    assert note in listed, "the note just created is not in GET /api/notes"
    # The page is static: it documents the API rather than rendering notes.
    _, _, page = get("/")
    assert text.encode() not in page


def test_two_notes_appear_side_by_side():
    first, second = create(unique("together")), create(unique("together"))
    listed = notes()
    assert first in listed and second in listed


def test_the_journey_carries_the_apps_headers_at_every_step():
    status, headers, _ = get("/")
    assert status == 200
    assert_security_headers(headers, "step 1 (the page)")
    status, headers, _ = post_json("/api/notes", {"text": unique("headers")})
    assert status == 201 and headers["content-type"].startswith("application/json")
    assert_security_headers(headers, "step 2 (the write)")
    status, headers, _ = get("/api/notes")
    assert status == 200
    assert_security_headers(headers, "step 3 (the listing)")


def test_the_listing_is_json_end_to_end():
    status, headers, raw = get("/api/notes")
    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert isinstance(body_json(raw)["notes"], list)
