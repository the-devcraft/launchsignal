import hashlib
import json
import re
import secrets

import stripe
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import connection, transaction
from django.db.models import Count
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from core.api_errors import Conflict
from core.auditing import FetchPolicyError, normalized_url
from core.models import (
    Action,
    AuditEvent,
    AuditRun,
    BillingInvoice,
    Finding,
    Membership,
    Project,
    Workspace,
)
from core.payments import apply_event
from core.tasks import publish


def member(request, workspace_id, write=False):
    membership = get_object_or_404(Membership, workspace_id=workspace_id, user=request.user)
    if write and membership.role == "viewer":
        raise PermissionDenied("This workspace is read-only for your role")
    return membership


class WorkspaceInput(serializers.Serializer):
    name = serializers.CharField(max_length=100)


class ProjectInput(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    site_url = serializers.CharField(max_length=500)

    def validate_site_url(self, value):
        try:
            return normalized_url(value)
        except FetchPolicyError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class RunInput(serializers.Serializer):
    source = serializers.ChoiceField(choices=["fixture", "live"])
    fixture = serializers.ChoiceField(choices=["baseline", "healthy"], default="baseline")


class ActionInput(serializers.Serializer):
    state = serializers.ChoiceField(choices=["open", "in_progress", "resolved"])
    version = serializers.IntegerField(min_value=1)
    assignee_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class SessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = get_token(request)
        return Response(
            {
                "csrf_token": token,
                "user": {
                    "id": request.user.id,
                    "name": request.user.get_full_name() or request.user.username,
                }
                if request.user.is_authenticated
                else None,
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        username, password = request.data.get("username"), request.data.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            raise ValidationError("Username and password are required")
        if len(username) > 150 or len(password) > 200:
            raise ValidationError("Invalid credentials")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials"}, status=401)
        login(request, user)
        return Response(
            {
                "csrf_token": get_token(request),
                "user": {
                    "id": user.id,
                    "name": user.get_full_name() or user.username,
                },
            }
        )


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"ok": True})


class WorkspacesView(APIView):
    def get(self, request):
        return Response(
            list(
                Membership.objects.filter(user=request.user)
                .select_related("workspace")
                .values("workspace_id", "workspace__name", "role")
            )
        )

    def post(self, request):
        data = WorkspaceInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            workspace = Workspace.objects.create(**data.validated_data)
            Membership.objects.create(workspace=workspace, user=request.user, role="owner")
            AuditEvent.objects.create(
                workspace=workspace,
                actor=request.user,
                kind="workspace.created",
                object_id=str(workspace.id),
            )
        return Response({"id": workspace.id, "name": workspace.name}, status=201)


class ProjectsView(APIView):
    def get(self, request, workspace_id):
        member(request, workspace_id)
        rows = Project.objects.filter(workspace_id=workspace_id).annotate(run_count=Count("runs"))
        return Response(
            list(
                rows.order_by("-created_at").values(
                    "id", "name", "site_url", "run_count", "created_at"
                )[:100]
            )
        )

    def post(self, request, workspace_id):
        member(request, workspace_id, write=True)
        data = ProjectInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            project = Project.objects.create(workspace_id=workspace_id, **data.validated_data)
            AuditEvent.objects.create(
                workspace_id=workspace_id,
                actor=request.user,
                kind="project.created",
                object_id=str(project.id),
            )
        return Response(
            {"id": project.id, "name": project.name, "site_url": project.site_url}, status=201
        )


class RunsView(APIView):
    def get(self, request, workspace_id, project_id):
        member(request, workspace_id)
        project = get_object_or_404(Project, id=project_id, workspace_id=workspace_id)
        return Response(
            list(
                project.runs.order_by("-created_at").values(
                    "id",
                    "status",
                    "source",
                    "fixture",
                    "score",
                    "attempts",
                    "error_code",
                    "created_at",
                    "finished_at",
                    "duration_ms",
                )[:50]
            )
        )

    def post(self, request, workspace_id, project_id):
        member(request, workspace_id, write=True)
        data = RunInput(data=request.data)
        data.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", key):
            raise ValidationError("A bounded Idempotency-Key header is required")
        fingerprint = hashlib.sha256(
            json.dumps(data.validated_data, sort_keys=True).encode()
        ).hexdigest()
        with transaction.atomic():
            project = get_object_or_404(
                Project.objects.select_for_update(), id=project_id, workspace_id=workspace_id
            )
            run = AuditRun.objects.filter(project=project, request_key=key).first()
            if run:
                if run.fingerprint != fingerprint:
                    raise Conflict("Idempotency key has conflicting audit options")
                return Response({"id": run.id, "status": run.status, "replayed": True})
            run = AuditRun.objects.create(
                project=project,
                requested_by=request.user,
                request_key=key,
                fingerprint=fingerprint,
                **data.validated_data,
            )
            AuditEvent.objects.create(
                workspace_id=workspace_id,
                actor=request.user,
                kind="audit.requested",
                object_id=str(run.id),
            )
            transaction.on_commit(lambda: publish(run.id))
        return Response({"id": run.id, "status": "pending", "replayed": False}, status=202)


class FindingsView(APIView):
    def get(self, request, workspace_id, run_id):
        member(request, workspace_id)
        run = get_object_or_404(AuditRun, id=run_id, project__workspace_id=workspace_id)
        rows = Finding.objects.filter(run=run).select_related("action").order_by("severity", "code")
        return Response(
            [
                {
                    "id": item.id,
                    "code": item.code,
                    "severity": item.severity,
                    "title": item.title,
                    "explanation": item.explanation,
                    "recommendation": item.recommendation,
                    "action": {
                        "state": item.action.state,
                        "version": item.action.version,
                        "assignee_id": item.action.assignee_id,
                    },
                }
                for item in rows
            ]
        )


class ActionView(APIView):
    def patch(self, request, workspace_id, finding_id):
        member(request, workspace_id, write=True)
        data = ActionInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            action = get_object_or_404(
                Action.objects.select_for_update(of=("self",)),
                finding_id=finding_id,
                finding__run__project__workspace_id=workspace_id,
            )
            if action.version != data.validated_data["version"]:
                raise Conflict("Action changed; reload before updating")
            action.state = data.validated_data["state"]
            if "assignee_id" in data.validated_data:
                assignee = data.validated_data["assignee_id"]
                if (
                    assignee is not None
                    and not Membership.objects.filter(
                        workspace_id=workspace_id, user_id=assignee
                    ).exists()
                ):
                    raise ValidationError("Assignee must belong to this workspace")
                action.assignee_id = assignee
            action.version += 1
            action.save()
            AuditEvent.objects.create(
                workspace_id=workspace_id,
                actor=request.user,
                kind=f"action.{action.state}",
                object_id=str(finding_id),
            )
        return Response({"state": action.state, "version": action.version})


class ActivityView(APIView):
    def get(self, request, workspace_id):
        member(request, workspace_id)
        return Response(
            list(
                AuditEvent.objects.filter(workspace_id=workspace_id)
                .order_by("-id")
                .values("id", "kind", "object_id", "created_at")[:50]
            )
        )


class BillingView(APIView):
    def get(self, request, workspace_id):
        role = member(request, workspace_id)
        if role.role != "owner":
            raise PermissionDenied("Billing requires workspace ownership")
        return Response(
            list(
                BillingInvoice.objects.filter(workspace_id=workspace_id)
                .order_by("-updated_at")
                .values("provider_id", "currency", "amount_due", "amount_paid", "status")[:100]
            )
        )


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhook(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not settings.STRIPE_WEBHOOK_SECRET:
            return Response({"detail": "Payment integration is not configured"}, status=503)
        if len(request.body) > 65_536:
            raise ValidationError("Webhook payload too large")
        try:
            stripe.Webhook.construct_event(
                request.body,
                request.headers.get("Stripe-Signature", ""),
                settings.STRIPE_WEBHOOK_SECRET,
                tolerance=300,
            )
        except (ValueError, stripe.SignatureVerificationError):
            return Response({"detail": "Invalid webhook signature"}, status=400)
        return Response(apply_event(json.loads(request.body), request.body))


class MembersView(APIView):
    def get(self, request, workspace_id):
        member(request, workspace_id)
        return Response(
            [
                {"id": item.user_id, "name": item.user.get_full_name() or item.user.username}
                for item in Membership.objects.filter(workspace_id=workspace_id)
                .select_related("user")
                .order_by("id")[:100]
            ]
        )


def liveness(request):
    return HttpResponse("ok", content_type="text/plain")


def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return HttpResponse("ready", content_type="text/plain")
    except Exception:
        return HttpResponse("unavailable", status=503, content_type="text/plain")


def metrics(request):
    if not settings.METRICS_TOKEN or not secrets.compare_digest(
        request.headers.get("Authorization", ""), f"Bearer {settings.METRICS_TOKEN}"
    ):
        return HttpResponse(status=403)
    from core.telemetry import JOBS

    counts = dict(AuditRun.objects.values_list("status").annotate(count=Count("id")))
    for state in AuditRun.Status.values:
        JOBS.labels(state).set(counts.get(state, 0))
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
