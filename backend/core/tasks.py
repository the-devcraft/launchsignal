import http.client
import logging
import time
import uuid
from datetime import timedelta
from pathlib import Path

from billiard.exceptions import SoftTimeLimitExceeded
from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.auditing import FetchPolicyError, analyze, fetch_html
from core.models import Action, AuditEvent, AuditRun, Finding
from core.telemetry import AUDIT_LATENCY, AUDITS

logger = logging.getLogger("launchsignal.worker")


def publish(run_id):
    try:
        execute_audit.delay(str(run_id))
    except Exception:
        # The database job is durable; beat will retry publication without losing the request.
        logger.warning("audit.publish_deferred", extra={"run_id": str(run_id)})


@shared_task(name="core.tasks.dispatch_pending")
def dispatch_pending():
    now = timezone.now()
    eligible = (
        AuditRun.objects.filter(
            Q(status="pending") & (Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
            | Q(status="running", lease_until__lt=now)
        )
        .order_by("created_at")
        .values_list("id", flat=True)[:100]
    )
    for run_id in list(eligible):
        publish(run_id)


@shared_task(name="core.tasks.execute_audit", acks_late=True, soft_time_limit=20, time_limit=30)
def execute_audit(run_id):
    started = time.perf_counter()
    with transaction.atomic():
        run = (
            AuditRun.objects.select_for_update().select_related("project").filter(id=run_id).first()
        )
        now = timezone.now()
        if not run or run.status in ("succeeded", "failed"):
            return "ignored"
        if run.status == "running" and run.lease_until and run.lease_until > now:
            return "leased"
        if run.next_attempt_at and run.next_attempt_at > now:
            return "delayed"
        if run.attempts >= 3:
            run.status, run.error_code = "failed", "retry_budget_exhausted"
            run.finished_at = now
            run.lease_token, run.lease_until = None, None
            run.save()
            AuditEvent.objects.create(
                workspace_id=run.project.workspace_id,
                actor_id=run.requested_by_id,
                kind="audit.failed",
                object_id=str(run.id),
            )
            AUDITS.labels("exhausted").inc()
            return "exhausted"
        token = uuid.uuid4()
        run.status, run.lease_token = "running", token
        run.lease_until = now + timedelta(seconds=45)
        run.attempts += 1
        run.save()
    try:
        if run.source == "fixture":
            # Choices are validated at the API boundary; no caller-supplied path is opened.
            if run.fixture not in ("baseline", "healthy"):
                raise FetchPolicyError("invalid_fixture")
            html = (Path(__file__).parent / "fixtures" / f"{run.fixture}.html").read_text()
        else:
            html = fetch_html(run.project.site_url)
        score, findings = analyze(html)
        error = None
    except FetchPolicyError as exc:
        error = str(exc)
    except (OSError, TimeoutError, http.client.HTTPException, SoftTimeLimitExceeded):
        error = "upstream_unavailable"
    with transaction.atomic():
        current = AuditRun.objects.select_for_update().get(id=run_id)
        if current.lease_token != token or current.lease_until <= timezone.now():
            return "stale"
        if error:
            retry = error == "upstream_unavailable" and current.attempts < 3
            current.status = "pending" if retry else "failed"
            current.error_code = error
            current.next_attempt_at = timezone.now() + timedelta(seconds=2**current.attempts)
            if not retry:
                current.finished_at = timezone.now()
        else:
            rows = [Finding(run=current, **item) for item in findings]
            Finding.objects.bulk_create(rows)
            Action.objects.bulk_create([Action(finding=item) for item in rows])
            current.status, current.score, current.error_code = "succeeded", score, ""
            current.finished_at = timezone.now()
        current.duration_ms = round((time.perf_counter() - started) * 1000)
        current.lease_token, current.lease_until = None, None
        current.save()
        AuditEvent.objects.create(
            workspace_id=run.project.workspace_id,
            actor_id=run.requested_by_id,
            kind=f"audit.{current.status}",
            object_id=str(run.id),
        )
    AUDITS.labels(current.status).inc()
    AUDIT_LATENCY.observe(time.perf_counter() - started)
    logger.info(
        "audit.completed",
        extra={"run_id": str(run.id), "status": current.status, "duration_ms": current.duration_ms},
    )
    return current.status
