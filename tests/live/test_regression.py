"""Regression: decided behaviour that must not come back.

Each test names the decision it protects, so a failure says what changed
rather than just which assertion moved. Read-only where it can be: the
writes it does make are its own notes, and it never assumes the list holds
only them (the dev/staging controls run in parallel against one pod).

    BASE_URL=https://localhost:18443 REQUESTS_CA_BUNDLE=ca.crt pytest tests/live/test_regression.py
"""

from .client import (
    assert_security_headers,
    body_json,
    call,
    create,
    get,
    notes,
    post_json,
    unique,
)


def test_note_text_is_trimmed_at_the_edges():
    """Decided: stored text is stripped, so the same note posted twice with
    different padding is one value, not two."""
    text = unique("trim")
    note = create(f"  {text}  ")
    assert note["text"] == text


def test_listing_is_an_object_under_notes():
    """Decided: GET /api/notes answers {"notes": [...]} — an envelope, so a
    future pagination or metadata field can be added without breaking the
    clients that read it."""
    status, _, raw = get("/api/notes")
    assert status == 200
    assert set(body_json(raw)) == {"notes"}


def test_healthz_is_exactly_status_ok():
    """Decided: the probe's body is the single key the Rollout's analysis
    and the health watch assert on. Extra keys are for another endpoint."""
    _, _, raw = get("/healthz")
    assert body_json(raw) == {"status": "ok"}


def test_empty_and_whitespace_text_are_refused():
    """Decided: a note must carry something; whitespace is nothing."""
    for text in ("", "   ", "\t\n"):
        status, _, _ = post_json("/api/notes", {"text": text})
        assert status == 400, f"{text!r} was accepted"


def test_a_non_string_text_is_refused():
    """Decided: {"text": 5} is a bad request, not a 500 and not "5"."""
    for text in (5, None, True, ["a"], {"a": 1}):
        status, _, _ = post_json("/api/notes", {"text": text})
        assert status == 400, f"{text!r} was accepted"


def test_deleting_the_collection_is_still_refused():
    """Decided: there is no bulk delete. A future one has to add it
    deliberately, and this test is where that shows up."""
    assert call("DELETE", "/api/notes")[0] == 405


def test_creating_answers_201_with_the_note():
    """Decided: 201 with the created note (id and trimmed text), not 200
    with the whole collection."""
    text = unique("created")
    status, _, raw = post_json("/api/notes", {"text": text})
    assert status == 201
    assert body_json(raw) == {"id": body_json(raw)["id"], "text": text}
    assert all(note["text"] != f"  {text}  " for note in notes())


def test_the_page_documents_the_endpoints():
    """Decided: the index page names the service and lists the API the
    suites and the users work through."""
    _, _, raw = get("/")
    for marker in (b"flask-gates-demo", b"/api/notes", b"/healthz"):
        assert marker in raw, f"{marker!r} is not on the index page"


def test_responses_are_never_cacheable():
    """Decided: Cache-Control: no-store everywhere — notes are per-process
    state, so a cached response would be wrong, not just stale."""
    for path in ("/", "/healthz", "/api/notes", "/no-such-path"):
        status, headers, _ = get(path)
        assert status in (200, 404)
        assert_security_headers(headers, path)
