"""Runs against the real image (TARGET_URL, started by G3), not the test
client — this is what proves the built artifact serves the app."""

import json
import os
import urllib.error
import urllib.request

import pytest

BASE = os.environ.get("TARGET_URL", "").rstrip("/")

pytestmark = pytest.mark.skipif(not BASE, reason="TARGET_URL not set (G3 sets it to the running image)")


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 — fixed http://127.0.0.1 target
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def test_health():
    status, _, body = call("GET", "/healthz")
    assert status == 200 and json.loads(body) == {"status": "ok"}


def test_note_round_trip():
    status, _, body = call("POST", "/api/notes", {"text": "integration"})
    assert status == 201
    note = json.loads(body)
    status, _, body = call("GET", "/api/notes")
    assert status == 200 and note in json.loads(body)["notes"]


def test_rejects_invalid_input():
    assert call("POST", "/api/notes", {"text": ""})[0] == 400


def test_security_headers():
    _, headers, _ = call("GET", "/")
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in headers["Content-Security-Policy"]
