# Security model

## Included controls

- Authentication, CSRF-protected login/logout and mutations; HTTP-only sessions; secure cookies when `DJANGO_DEBUG=false`.
- Per-request workspace membership checks, scoped nested-resource lookups, role restrictions and member-only assignment.
- Anonymous login throttling. Compose uses a shared Redis cache; local test mode uses process-local memory. Apply trusted ingress limits before deploying behind a proxy.
- HTTPS-only live audit URLs, exact operator allowlists, all-address public-IP validation, DNS pinning with original-host TLS verification, no redirects/proxies, 512 KiB HTML limit and bounded worker execution.
- Raw-body payment signatures, narrow event acceptance, integer amount validation, idempotency fingerprints and transactional event/invoice updates.
- Protected metrics; route templates rather than resource IDs in metric labels; bounded rotating logs. Application logs do not include credentials or payment bodies.
- Non-root application containers, internal-only database/broker ports, immutable action references and read-only collector access to logs. GitHub Actions have read-only repository permissions and pinned action revisions.

## Before internet exposure

The supplied Compose file is a **local evaluation setup**. DEBUG is enabled for local cookies, PostgreSQL's bootstrap role has database-owner privileges, Redis is isolated on the Compose network without authentication, and telemetry storage is ephemeral. It must not be treated as a production deployment manifest.

Deploy behind HTTPS ingress with explicit hosts/origins, a 1 MiB request cap and network rate limiting. Set DEBUG=false; configure HSTS/redirects and trusted forwarded-protocol handling only for the actual proxy. Create separate least-privilege migration/runtime database roles, restrict egress for live audits, secure Redis, isolate telemetry and use managed secrets. Disable/remove the demo account and fixtures. Add backup retention and test restore, SSO/account provisioning, workspace lifecycle/retention policies and operational alerts before handling real client data.

Sentry is opt-in and disables default PII, local variable capture and request body capture. Review the provider's data handling and configure scrubbing for your deployment. OpenTelemetry can record route/SQL metadata; do not enable unrestricted payload instrumentation.

## Explicit limits

There is no RLS, MFA, invitation/password-reset system, anti-tampering database trigger, formal penetration test, compliance certification or zero-bug guarantee. Resolving an action is not evidence a website was fixed. The live fetcher does not run JavaScript or crawl a site. Rate limits depend on a correctly configured proxy/IP boundary. Malicious operators and compromised database credentials are outside the application tenancy boundary.

Report a suspected vulnerability privately to the repository owner through GitHub. Avoid including credentials, customer content or working exploits in public issues.
