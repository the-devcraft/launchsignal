# API contract

All paths below are under `/api`, without a trailing slash. JSON responses use `Cache-Control: no-store` and `X-Request-ID`. Session cookies are HTTP-only; unsafe browser requests require `X-CSRFToken` from the session endpoint. Fetch a fresh token after login because Django rotates it.

| Method / path | Purpose / contract |
| --- | --- |
| GET `/auth/session` | Anonymous-safe session and CSRF token |
| POST `/auth/login` | `{username, password}`; CSRF protected even before login; 10 anonymous attempts/IP/minute |
| POST `/auth/logout` | End the current session; CSRF required |
| GET/POST `/workspaces` | List memberships / create a workspace owned by the caller |
| GET `/workspaces/{w}/members` | Up to 100 workspace members; IDs and display names |
| GET/POST `/workspaces/{w}/projects` | Up to 100 sites / create `{name, site_url}` with HTTPS URL |
| GET/POST `/workspaces/{w}/projects/{p}/runs` | Latest 50 runs / queue `{source: "fixture"\|"live", fixture: "baseline"\|"healthy"}` |
| GET `/workspaces/{w}/runs/{r}/findings` | Snapshot findings and action state, version, assignee ID |
| PATCH `/workspaces/{w}/findings/{f}/action` | `{state, version, assignee_id?}`; states open/in_progress/resolved |
| GET `/workspaces/{w}/activity` | Latest 50 workspace events |
| GET `/workspaces/{w}/billing` | Latest 100 invoices; owner only |
| POST `/webhooks/stripe` | Signed provider snapshot event; no browser session required |
| GET `/health/live`, `/health/ready` | Process liveness / PostgreSQL connectivity |
| GET `/metrics` | `Authorization: Bearer <METRICS_TOKEN>`; internal access only |

Queue requests require `Idempotency-Key: <1–80 ASCII letters/digits/_/->`. First acceptance returns 202. An identical replay returns 200 with the same run ID; different options with the same key return 409. Idempotency is scoped to a project. Keys are retained with runs; there is no automatic expiry.

Error behavior: malformed input 400, unauthenticated session access 403, insufficient role 403, absent/inaccessible workspace or resource 404, conflicting state 409, rate limit 429, oversized request 413. Login failure returns 401; an unconfigured webhook returns 503. Webhooks over 64 KiB return 400; the general application body cap is 1 MiB. Deploy an ingress body limit as well.

### Minimal browser sequence

1. GET `/auth/session`, retaining cookies and `csrf_token`.
2. POST `/auth/login` with the token and credentials, then retain the rotated token.
3. GET `/workspaces`, choose a returned workspace, then GET its projects.
4. POST a run with a fresh idempotency key; poll the runs endpoint for completion.
5. GET findings; PATCH an action using the returned version.

### Stripe integration

Configure a **snapshot** destination for the three supported invoice events. Map an actual Stripe customer to a workspace with `BillingCustomer` using an operator-only Django shell; this is intentionally not a public API. Set the endpoint signing secret, register `/api/webhooks/stripe`, and test in Stripe test mode before live use. The handler verifies the raw body following [Stripe's webhook guidance](https://docs.stripe.com/webhooks). No Stripe API key is needed because the application does not initiate provider requests.
