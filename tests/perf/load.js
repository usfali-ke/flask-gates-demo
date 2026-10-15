// Performance: 10 virtual users for 30s against the deployed environment.
// verdict.py k6 decides: p95 within the SLO, <1% failed requests, >=99%
// checks passed.
//
// Read-only on purpose. The app has no accounts (this repo's suites run
// anonymously) and notes live in the pod's memory with a 1000-note cap
// (app.MAX_NOTES): a load test that wrote a note per iteration would fill
// the store within the 30s window, start getting 507s, fail its own
// 'create 201' check — and break every other control running against the
// same pod in parallel. Load hits the endpoints the page documents.
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL;

export const options = {
  vus: 10,
  duration: '30s',
};

export default function () {
  check(http.get(`${BASE}/healthz`), { 'healthz ok': (r) => r.status === 200 && r.json('status') === 'ok' });
  check(http.get(`${BASE}/`), { 'index 200': (r) => r.status === 200 });
  check(http.get(`${BASE}/api/notes`), { 'list 200': (r) => r.status === 200 });
  sleep(0.2);
}

export function handleSummary(data) {
  return { [__ENV.SUMMARY_OUT || 'k6-summary.json']: JSON.stringify(data) };
}
