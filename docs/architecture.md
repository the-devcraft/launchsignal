# Architecture and decisions

## Tenant boundary

A membership associates a Django user with one workspace and a role. Every workspace endpoint resolves that membership before reading data. Nested resources are resolved using both their identifier and the workspace identifier; possessing a UUID is never sufficient authorization. Viewers cannot write. Editors can operate audits and actions but cannot read billing. Customer mappings are managed by an operator, not client-supplied metadata.

Shared-schema tenancy keeps this evaluation deployment simple. PostgreSQL RLS would provide a second boundary, but requires reliable connection-level tenant context and carefully separated operator access. It is not enabled here. Tenant isolation tests cover outsiders, revoked memberships, nested resources and billing.

## Durable background delivery

The API locks the project, checks a unique `(project, request_key)` pair and compares a request fingerprint. An accepted request records the job and activity in one PostgreSQL transaction. Publishing occurs after commit. Publication failure is logged, while a periodic dispatcher republishes due jobs from the database every 15 seconds.

Redis/Celery delivery is at least once. Each worker claims a run under a row lock, receives a random fencing token and a 45-second lease, then performs work outside the transaction. Completion checks both token and lease before atomically creating findings/actions and recording the result. Duplicate workers return without repeating committed effects. A killed worker's expired lease is recoverable; three claims exhaust the budget. Live network work has per-socket timeouts and prefork Celery soft/hard limits of 20/30 seconds. The local solo worker cannot enforce prefork hard time limits.

The dispatcher is intentionally small and scans at most 100 jobs per tick. This favors inspectability over a general-purpose workflow engine. High-volume deployments should shard dispatch, measure backlog age and move to a dedicated outbox/dispatcher service when justified.

## Concurrent action editing

Actions carry an incrementing version. A writer supplies the version they read. The API locks the action, compares versions, validates the assignee's workspace membership, updates state and records activity atomically. A stale writer receives HTTP 409 and must reload. Findings remain immutable snapshots at the application level; there are no mutation endpoints for audit findings. Database administrators can still modify records, so this is not a tamper-proof audit ledger.

## Payment-event projection

The webhook verifies the Stripe signature against original bytes with a five-minute tolerance before interpreting invoice fields. PostgreSQL transaction-scoped advisory locks serialize event/invoice references even when the target rows do not exist. Sorted lock acquisition prevents reference-order deadlocks. A customer row lock then scopes the event to a workspace. Unique provider IDs and a SHA-256 payload fingerprint make exact replay a no-op and conflicting replay a 409.

Supported snapshot events are `invoice.paid`, `invoice.payment_failed` and `invoice.voided`. Older or equal-time events cannot overwrite an existing invoice; the first received event wins ties. Paid/void states cannot be downgraded to a different terminal or open state. This deliberately conservative projection requires operator reconciliation for ambiguous equal-time provider events. It accepts USD/EUR/GBP integer amounts; it neither charges cards nor computes balances across currencies.

## Telemetry and scaling

One threaded Gunicorn API process keeps the process-local HTTP histogram/counter registry accurate. The authenticated metrics endpoint also reports durable job counts from PostgreSQL, so worker state is visible across processes. Worker-local attempt counters are not authoritative fleet metrics; worker durations are available in structured logs and traces. Horizontal API scaling requires per-instance scraping or a configured Prometheus multiprocess collector. Do not simply increase Gunicorn workers and expect aggregated counters.

The optional local stack uses file-based JSON log collection rather than mounting the Docker socket into a collector. Alloy tails bounded rotating application logs into Loki, scrapes the API into Mimir, and Grafana links a log trace ID to Tempo. Django and Celery export OTLP traces directly to Tempo. Sentry is independently opt-in. No third-party credentials are required to run fixture workflows.
