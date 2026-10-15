"""HTTP helpers for the suites that run against a deployed environment
(tests/live; README "Environment test runner").

Everything goes through the environment's TLS ingress (BASE_URL) the way a
browser would, with the standard library only: this repo declares no HTTP
client dependency and the test jobs sync the project's own lockfile, so
adding `requests` just for the suites would put a package in the app's
environment that the deployed image does not have.

    BASE_URL=https://localhost:18443 [REQUESTS_CA_BUNDLE=ca.crt] pytest tests/live/
"""

import json
import os
import ssl
import urllib.error
import urllib.request
import uuid

BASE = os.environ["BASE_URL"].rstrip("/")
TIMEOUT = 10

# The environment's ingress presents a certificate from a throwaway internal
# CA (tests/env/env-up.sh writes it). REQUESTS_CA_BUNDLE — the name
# env-up.sh exports, and the one django-gates-demo's suites use — names that
# CA; SSL_CERT_FILE is honoured too. With neither, the system store is used.
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")


def _context():
    return ssl.create_default_context(cafile=CA_BUNDLE) if CA_BUNDLE else ssl.create_default_context()


CONTEXT = _context()


def flatten(headers):
    """A plain, lower-cased dict: the suites compare exact header names."""
    return {name.lower(): value for name, value in headers.items()}


def call(method, path, body=None, *, raw=None, extra_headers=None):
    """(status, headers, body) for one request. An HTTP error status is
    returned rather than raised — the suites assert on the refusals too."""
    if raw is not None:
        data = raw if isinstance(raw, bytes) else raw.encode()
    elif body is not None:
        data = json.dumps(body).encode()
    else:
        data = None
    headers = dict(extra_headers or {})
    if data is not None:
        headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CONTEXT))
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            return response.status, flatten(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, flatten(error.headers), error.read()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def call_absolute(url):
    """GET an absolute URL without following redirects: the ingress's
    http → https redirect is what the smoke suite checks."""
    request = urllib.request.Request(url, method="GET")
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=CONTEXT))
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            return response.status, flatten(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, flatten(error.headers)


def get(path, **kwargs):
    return call("GET", path, **kwargs)


def post_json(path, body, **kwargs):
    return call("POST", path, body=body, **kwargs)


def body_json(raw):
    return json.loads(raw or b"null")


def notes():
    """The listing the page documents: GET /api/notes."""
    status, _, raw = get("/api/notes")
    assert status == 200, f"GET /api/notes answered {status}"
    return body_json(raw)["notes"]


def create(text):
    status, _, raw = post_json("/api/notes", {"text": text})
    assert status == 201, f"POST /api/notes answered {status}: {raw!r}"
    return body_json(raw)


def unique(prefix):
    return f"{prefix}-{uuid.uuid4()}"


# The headers the app puts on every response (app.SECURITY_HEADERS), stated
# here in full so the suites assert the deployed image's real values rather
# than importing the checkout's copy of them.
SECURITY_HEADERS = {
    "content-security-policy": "default-src 'none'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "permissions-policy": "geolocation=(), camera=(), microphone=()",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
    "cache-control": "no-store",
}


def assert_security_headers(headers, where):
    for name, value in SECURITY_HEADERS.items():
        assert headers.get(name) == value, f"{where}: {name} is {headers.get(name)!r}, expected {value!r}"
