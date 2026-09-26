"""A deliberately tiny notes service: just enough surface (a page, a JSON
API with input validation, a health check) for every DevSecOps gate to have
something real to test."""

import threading

from flask import Flask, jsonify, request

MAX_NOTES = 1000
MAX_TEXT = 500

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}

INDEX = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>flask-gates-demo</title></head>
<body>
<h1>flask-gates-demo</h1>
<p>A minimal notes API used to exercise the G1&ndash;G6 DevSecOps gates end to end.</p>
<ul>
<li><code>GET /api/notes</code> &mdash; list notes</li>
<li><code>POST /api/notes</code> &mdash; add a note: <code>{"text": "..."}</code></li>
<li><code>GET /healthz</code> &mdash; health check</li>
</ul>
</body>
</html>
"""


def create_app() -> Flask:
    app = Flask(__name__)
    notes: list[dict] = []
    lock = threading.Lock()

    @app.after_request
    def security_headers(response):
        response.headers.update(SECURITY_HEADERS)
        return response

    @app.get("/")
    def index():
        return INDEX, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.get("/api/notes")
    def list_notes():
        with lock:
            return jsonify(notes=list(notes))

    @app.post("/api/notes")
    def add_note():
        body = request.get_json(silent=True)
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            return jsonify(error=f"text must be a non-empty string of at most {MAX_TEXT} characters"), 400
        with lock:
            if len(notes) >= MAX_NOTES:
                return jsonify(error="note limit reached"), 507
            note = {"id": len(notes) + 1, "text": text.strip()}
            notes.append(note)
        return jsonify(note), 201

    return app
