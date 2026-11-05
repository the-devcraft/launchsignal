# Development notes

## Source and scope

LaunchSignal is an original portfolio implementation. No external project's application source or repository history was imported. Frameworks, packages and service images retain their own licenses. The project explores operational correctness at a useful, inspectable scale; it does not claim customer adoption, production incidents or commercial results.

Some Git author/committer timestamps are selected historical metadata. They are not evidence of implementation, verification or employment dates; dependency versions and GitHub server-side events have their own timelines. Logical commits describe implementation boundaries, not a claim that development took place over those historical weeks.

## Working locally without containers

Use Python 3.12+, PostgreSQL 17, Node 24 and pnpm 11.25.0. Install the locked dependencies, set the environment variables described in the README, migrate and seed. Start Redis and a normal Celery worker/beat for a representative background setup.

For a local-only smoke test without Redis, set `DJANGO_DEBUG=true` and `CELERY_BROKER_URL=memory://`, then run `python backend/manage.py demo_server`. This starts the development API and a real in-process Celery worker. It is not a production runtime and cannot model Redis durability, process isolation or prefork time limits. CI exercises the Redis-backed path.

Frontend API requests stay same-origin. `API_INTERNAL_URL` controls Next's rewrite at **build time**, so rebuild after changing it. Container builds use `http://api:8000`; local builds default to `http://127.0.0.1:8000`. Docker runs the standalone output; `pnpm dev` is appropriate for local UI development.

## Review expectations

Keep tenant boundaries explicit in every new query. Add negative authorization tests alongside happy paths. Treat queue delivery as at least once, money as integer minor units and provider input as untrusted until verified. Avoid fabricated performance claims: record hardware, workload and sample counts with benchmark results. CI success is bounded evidence, not proof of production readiness.

The end-to-end tests capture real screenshots from fixture workflows. Update those images when the interface changes, inspect desktop/mobile layouts and keep fixture labels visible. Do not use fabricated customer records or synthetic dashboards as evidence of production usage.
