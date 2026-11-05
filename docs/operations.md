# Operations runbook

## Startup and health

`docker compose up --build -d` runs migrations before serving API traffic. Seed with the tools profile only for local demos. Liveness reports process availability; readiness checks PostgreSQL, not the broker. A broker outage degrades immediate delivery but does not reject durable accepted audit requests. Confirm worker/beat health separately using logs and backlog age.

## Audit remains pending

1. Find the run ID from the API response/activity view. Inspect worker and dispatcher JSON logs using `docker compose logs worker beat`.
2. Check Redis connectivity. Restore Redis before republishing work; do not create replacement jobs with new request keys.
3. Confirm beat is running. It republishes due pending jobs and expired running leases every 15 seconds. A single deployment should run one beat instance.
4. If all three claims were exhausted, investigate `error_code` and logs before issuing an intentional new request. There is no silent infinite retry.

## Increased errors or latency

Use Grafana's Operations dashboard to compare request rate, p95 and 5xx ratio. Search Loki for `request_id` or a worker `run_id`; follow a non-zero `trace_id` to Tempo. Tracing is sampled, so not every request will have a stored trace. Check PostgreSQL availability and lock waits, then upstream host failures. Disable a problematic live-audit allowlist entry while investigating. Avoid logging raw bodies or session cookies during diagnosis.

## Payment mismatch or webhook rejection

Invalid signatures return 400 and make no billing changes. Confirm the destination secret and server clock; use original bytes when replaying a signed test request. Unknown customers need an operator-created mapping, not a metadata override. A conflicting provider event ID returns 409 for investigation. Duplicate exact bytes return 200 with `duplicate`. Older events are recorded but do not regress invoices. Equal-time ambiguities require manual provider comparison; the projection intentionally does not claim ledger completeness.

## Backup and restore

```sh
docker compose exec -T db pg_dump -U launchsignal -Fc launchsignal > launchsignal.dump
# Restore into a separate empty verification database, never directly over live data:
docker compose exec db createdb -U launchsignal launchsignal_restore
docker compose exec -T db pg_restore -U launchsignal -d launchsignal_restore < launchsignal.dump
```

Verify row counts, membership boundaries and a fixture audit against the restored database before relying on a backup. SQL backups contain user and workspace data: encrypt them, restrict access and enforce retention. The repository includes no client data or credentials.

## Observability profile

API/worker JSON logs rotate at 5 MB with two backups per service. Alloy tails the shared log volume without access to the Docker socket. HTTP metrics come from one threaded API process; durable job state is read from PostgreSQL. Mimir/Loki/Tempo are local evaluation stores, with Tempo retaining 24h. Grafana is loopback-only and requires a configured password. Set the OTLP endpoint to the Tempo service only when the observability profile is enabled.

Use `python scripts/observability_smoke.py` to verify all three ingestion paths after creating app traffic. CI executes this check with the actual Compose services. External Sentry delivery requires your own DSN and is outside fixture verification.
