// G3 performance: 10 virtual users for 30s against the running image.
// verdict.py k6 decides: p95 within the SLO, <1% failed requests, >=99% checks.
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.TARGET_URL;

export const options = {
  vus: 10,
  duration: '30s',
};

export default function () {
  check(http.get(`${BASE}/`), { 'index 200': (r) => r.status === 200 });
  check(http.get(`${BASE}/api/notes`), { 'list 200': (r) => r.status === 200 });
  check(http.get(`${BASE}/healthz`), { 'healthz ok': (r) => r.status === 200 && r.json('status') === 'ok' });
  sleep(0.2);
}

export function handleSummary(data) {
  return { [__ENV.SUMMARY_OUT || 'k6-summary.json']: JSON.stringify(data) };
}
