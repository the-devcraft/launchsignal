import uuid

from django.conf import settings
from django.db import models


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner"
        EDITOR = "editor"
        VIEWER = "viewer"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=Role.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "user"], name="unique_member")]


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    site_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="runs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_key = models.CharField(max_length=80)
    fingerprint = models.CharField(max_length=64)
    source = models.CharField(max_length=12, choices=[("fixture", "fixture"), ("live", "live")])
    fixture = models.CharField(max_length=12, default="baseline")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    next_attempt_at = models.DateTimeField(null=True)
    score = models.PositiveSmallIntegerField(null=True)
    error_code = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    duration_ms = models.PositiveIntegerField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "request_key"], name="unique_audit_request"),
            models.CheckConstraint(condition=models.Q(score__lte=100), name="score_range"),
        ]
        indexes = [models.Index(fields=["status", "next_attempt_at"])]


class Finding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AuditRun, on_delete=models.CASCADE, related_name="findings")
    code = models.CharField(max_length=50)
    severity = models.CharField(max_length=10)
    title = models.CharField(max_length=160)
    explanation = models.TextField()
    recommendation = models.TextField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "code"], name="unique_run_finding")]


class Action(models.Model):
    finding = models.OneToOneField(Finding, on_delete=models.CASCADE, related_name="action")
    state = models.CharField(max_length=16, default="open")
    version = models.PositiveIntegerField(default=1)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(state__in=["open", "in_progress", "resolved"]),
                name="action_state",
            )
        ]


class AuditEvent(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=60)
    object_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)


class BillingCustomer(models.Model):
    workspace = models.OneToOneField(Workspace, on_delete=models.PROTECT)
    provider_id = models.CharField(max_length=100, unique=True)


class BillingInvoice(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    provider_id = models.CharField(max_length=100, unique=True)
    currency = models.CharField(max_length=3)
    amount_due = models.PositiveBigIntegerField()
    amount_paid = models.PositiveBigIntegerField()
    status = models.CharField(max_length=16)
    provider_created = models.BigIntegerField()
    updated_at = models.DateTimeField(auto_now=True)


class BillingEvent(models.Model):
    provider_id = models.CharField(max_length=100, unique=True)
    fingerprint = models.CharField(max_length=64)
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    kind = models.CharField(max_length=60)
    applied = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
