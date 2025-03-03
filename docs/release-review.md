# Release review

The review focused on behavior a technical reviewer can inspect and reproduce, rather than decorative repository activity.

| Concern | Correction / evidence |
| --- | --- |
| Cross-workspace access through nested IDs | Scope every nested lookup; test a user who belongs to both workspaces, not only an outsider |
| Duplicate background delivery | Persist requests, use project-scoped idempotency and fenced leases; exercise simultaneous acceptance and a real Celery worker |
| Competing payment deliveries | Serialize event/invoice references and customer updates; concurrent replay test produces one invoice/event |
| SDK-version assumptions | Verify a real Stripe HMAC header and parse verified raw JSON independently of SDK object conversion helpers |
| Lost task edits | Row-lock the action only, reject stale versions and validate workspace membership for assignees |
| Unsafe or malformed live URLs | Reject control characters, encode international paths, preserve IPv6 authority and pin public DNS results for TLS fetches |
| Stale UI requests after switching sites | Invalidate previous run/finding responses; disable scope changes while a mutation is being committed |
| UI readability and mobile overflow | Contrast corrections driven by automated WCAG checks, genuine desktop/mobile screenshots and a no-horizontal-overflow assertion |
| Unnecessary production dependencies | Separate runtime package closure from test, lint and audit tooling |
| Misleading positioning | State the five-rule audit scope, manual resolution semantics, synthetic billing data and deployment boundaries explicitly |

This is an internal implementation review, not an independent security audit. The application demonstrates full-stack delivery and failure handling within a bounded portfolio scope. Real customer operation would additionally require the deployment controls and operational processes described in the security guide.
