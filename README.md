# flask-gates-demo

A deliberately tiny Flask notes API whose only job is to go through every
DevSecOps control gate (G1–G6) for real, end to end, and report each
decision to the security dashboard.

```
GET  /            page
GET  /healthz     {"status": "ok"}
GET  /api/notes   list notes (in memory)
POST /api/notes   {"text": "..."}  → 201, or 400 on invalid input
```

Run locally: `uv sync && uv run gunicorn -b 127.0.0.1:8080 app.wsgi:app`.
Tests: `uv run pytest tests/unit`; `TARGET_URL=http://127.0.0.1:8080 uv run pytest tests/integration`.

## Gates

Every gate has the same shape: one job per control, all in parallel. Each
control job ends in `.github/scripts/verdict.py`, which applies that
control's threshold and fails the job, so a red job is a failed control.
The last job of the gate combines the controls (`.github/scripts/gate.py`),
uploads `gate-result-<G>` for the dashboard, and fails unless all passed.

```
PR ─ devsecops-pr ── G1 merge gate ── merge
                                        │
main ─ devsecops-build ── G2 artifact gate ── G3 pre-production gate (devsecops-uat)
                          (build once, sign)   (tests that exact digest)
                                        │
Actions → devsecops-release ── G4 release approval ── G5 deployment gate ── GitOps commit
   (change request issue)      (environment +          (provenance, config,     │
                                dashboard decision)     deploy)                 ▼
                                                                  Argo CD → Kyverno (G6) → canary
```

| Gate | Controls (job → criterion) |
|---|---|
| G1 | reviewers, unit-tests, sast (semgrep), secrets (gitleaks), commits-signed |
| G2 | build (digest-pinned bases, reproducible), sca, iac (checkov), image-scan, sbom, sign (cosign + SLSA provenance) |
| G3 | functional (unit + integration against the image), performance (k6), coverage (≥80%), dast (ZAP baseline), compliance (trivy config) |
| G4 | protected environment `release-approval` + dashboard decision on the change request |
| G5 | provenance verified, target config controlled (kubeconform), deploy via GitOps only |

## Releasing

1. Open a **Change request** issue (issue form); someone other than you adds
   `change-approved` and `readiness-approved`.
2. Actions → **devsecops-release** → Run workflow with the issue number.
3. Approve the `release-approval` deployment when GitHub asks.
