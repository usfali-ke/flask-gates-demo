import pytest

from app import MAX_NOTES, MAX_TEXT, SECURITY_HEADERS, create_app


@pytest.fixture
def client():
    return create_app().test_client()


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"flask-gates-demo" in r.data


def test_healthz(client):
    assert client.get("/healthz").get_json() == {"status": "ok"}


def test_security_headers_on_every_response(client):
    for r in (client.get("/"), client.get("/api/notes"), client.get("/missing")):
        for name, value in SECURITY_HEADERS.items():
            assert r.headers[name] == value


def test_add_and_list(client):
    r = client.post("/api/notes", json={"text": "  hello  "})
    assert r.status_code == 201
    assert r.get_json() == {"id": 1, "text": "hello"}
    assert client.get("/api/notes").get_json() == {"notes": [{"id": 1, "text": "hello"}]}


@pytest.mark.parametrize("body", [None, [], {}, {"text": ""}, {"text": "   "}, {"text": 5}, {"text": "x" * (MAX_TEXT + 1)}])
def test_rejects_invalid_notes(client, body):
    r = client.post("/api/notes", json=body) if body is not None else client.post("/api/notes", data="not json")
    assert r.status_code == 400
    assert client.get("/api/notes").get_json() == {"notes": []}


def test_note_limit(client):
    for i in range(MAX_NOTES):
        assert client.post("/api/notes", json={"text": str(i)}).status_code == 201
    assert client.post("/api/notes", json={"text": "one too many"}).status_code == 507


def test_method_not_allowed(client):
    assert client.delete("/api/notes").status_code == 405
