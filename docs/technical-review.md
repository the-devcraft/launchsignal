# Technical and portfolio review

This is an internal code, behavior and presentation review, not an independent human audit or a guarantee that every possible defect has been eliminated.

## Findings corrected

| Priority | Finding | Correction | Verification |
| --- | --- | --- | --- |
| P1 | Logout retained workspace state; re-login rendered the dashboard before fresh workspace discovery finished | Clear session-scoped data, invalidate outstanding responses and await fresh workspace discovery before showing authenticated UI | Delayed-workspace browser regression failed before the fix and passed afterwards |
| P2 | Mobile CSS hid account controls, including sign-out | Keep identity and sign-out accessible at narrow widths | Mobile sign-out regression failed before the fix and passed afterwards; screenshot refreshed |
| P2 | Empty primary headings passed the audit | Require exactly one non-empty H1 | Three empty-heading cases failed before the fix and passed afterwards |
| P2 | Relative/script canonical URLs passed the audit | Require exactly one usable absolute HTTPS canonical URL | Four invalid-canonical cases failed before the fix and passed afterwards |
| P2 | A provider timestamp outside PostgreSQL bigint range caused a database error | Validate the persisted integer range before mutation | Overflow regression now produces a validation error with no invoice/event writes |
| P2 | A later event could silently change an invoice's currency | Reject denomination conflicts atomically | Regression preserves the original currency and event count |
| P2 | Arbitrary HTTP method strings created unbounded metric labels | Map methods outside the supported set to `OTHER` | Distinct untrusted methods cannot create distinct label series |

The session finding concerns client state during authentication transitions. Existing server-side tenant authorization tests continued to pass; no server-side tenant-query bypass was found in this review.

## Verification

- Original implementation: no third-party application's source tree or Git history was imported. Framework and package licenses remain applicable.
- Local PostgreSQL suite: **55 tests passed**, **97.86% combined statement/branch coverage**.
- Browser suite: **four workflows passed**, including the two newly reproduced regressions, plus desktop/mobile accessibility scans.
- Strict TypeScript, ESLint and optimized frontend build passed. CI repeats the checks, tests Python 3.12/3.13 with Redis, builds Compose and verifies metric/log/trace ingestion.
- Screenshots show the running application with synthetic data, not customer deployments or revenue.

## Hiring presentation

The strongest evidence is inspectable behavior: scoped authorization, database locking, repeat-safe delivery, payment-event validation, executable tests and an operating runbook. Present those capabilities and the design tradeoffs.

This is a bounded portfolio application: five HTML rules, manual action resolution and a webhook invoice projection. It is not a comprehensive marketing suite, a checkout/general ledger or proof of operating a customer production service. Keep those boundaries visible.

Selected historical Git timestamps are documented metadata, not proof of historical delivery or employment. Dependencies and GitHub's server-side timeline must not be used to imply development happened in a different year.

## Remaining limits

- External Stripe/Sentry account delivery, production load, independent penetration testing and container-image vulnerability scanning have not been performed. Follow the security guide before real customer use.
- ESLint 9 is retained because the installed React ESLint plugin's declared peer range excludes ESLint 10. The package manager reports ESLint 9 as unsupported. This is development-tool maintenance debt; a compatible framework/plugin upgrade and passing lint run are required. Peer constraints have not been silently overridden.
- No whole-internet plagiarism search or uniqueness certification was performed. Originality refers to the implementation created here and the absence of imported third-party application source/history.

[CI](https://github.com/the-devcraft/launchsignal/actions) · [Security](security.md) · [Architecture](architecture.md)
