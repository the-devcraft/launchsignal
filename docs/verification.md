# Verification evidence

This file records observed checks, not a promise of a flaw-free system.

## Local checks

- PostgreSQL 17.11; Python 3.12.14; Windows loopback-only development services.
- Backend: 43 tests passed in the initial expanded suite, including concurrent audit acceptance, concurrent payment replay and real in-process Celery delivery. The suite continues to grow with fixes; CI is the current source of truth.
- Frontend: strict TypeScript, ESLint and the optimized Next build passed.
- Browser: real login, assignment/status changes, site creation, queued baseline/healthy audits, workspace switching, billing isolation and logout. Automated WCAG A/AA desktop/mobile checks caught and drove contrast fixes.
- Python dependency audit found no known vulnerabilities in the locked versions at verification time. This is not a guarantee against undisclosed vulnerabilities.

## CI checks

The workflow validates Python 3.12/3.13 with PostgreSQL and Redis, builds frontend/backend containers, runs browser/accessibility checks against Compose and verifies actual metric/log/trace ingestion. Consult the [workflow runs](https://github.com/the-devcraft/launchsignal/actions/workflows/ci.yml) for the final commit's outcomes rather than assuming a checked-in workflow has passed.

## Material limits

The reproducible [local baseline](baseline.json) measures 100 sequential authenticated findings reads through the Next proxy after 10 warm-up requests: p50 41.27 ms, p95 155.47 ms. This Windows development measurement includes local session/database work and is not a production throughput claim. The API test separately enforces a three-query budget for the findings endpoint.

Docker is unavailable in the local Windows session; full container and Grafana-stack runtime checks are performed in CI. No external Sentry DSN, Stripe account, live payment, production traffic, independent penetration test or third-party audit was used. Live network behavior is boundary-tested using controlled HTTP/DNS mocks; fixture browser tests make no external website calls. Coverage percentages measure exercised code, not completeness or absence of defects.
