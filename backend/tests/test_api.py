from unittest.mock import patch

import pytest
from core.models import Action, AuditEvent, AuditRun, Membership
from core.tasks import execute_audit
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_login_requires_csrf_and_rotates_token(tenant):
    client = APIClient(enforce_csrf_checks=True)
    assert (
        client.post(
            "/api/auth/login", {"username": "owner", "password": "test-password-123"}
        ).status_code
        == 403
    )
    token = client.get("/api/auth/session").json()["csrf_token"]
    response = client.post(
        "/api/auth/login",
        {"username": "owner", "password": "test-password-123"},
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    assert response.json()["csrf_token"] != token
    assert client.post("/api/auth/logout").status_code == 403
    token = response.json()["csrf_token"]
    assert client.post("/api/auth/logout", HTTP_X_CSRFTOKEN=token).status_code == 200
    assert client.get("/api/workspaces").status_code == 403


def test_invalid_credentials_and_throttle(tenant):
    client = APIClient()
    for _ in range(10):
        assert (
            client.post("/api/auth/login", {"username": "owner", "password": "wrong"}).status_code
            == 401
        )
    assert client.post("/api/auth/login", {}).status_code == 429


@pytest.mark.parametrize(
    "payload", [{}, {"username": []}, {"username": "x" * 151, "password": "x"}]
)
def test_bad_login_input(payload):
    assert APIClient().post("/api/auth/login", payload, format="json").status_code == 400


def test_membership_scopes_and_revocation(tenant):
    c, base = tenant["client"], tenant["base"]
    assert len(c.get("/api/workspaces").json()) == 1
    assert c.get(f"/api/workspaces/{tenant['foreign'].id}/projects").status_code == 404
    assert c.get(base + "/members").json() == [{"id": tenant["user"].id, "name": "owner"}]
    Membership.objects.filter(user=tenant["user"]).delete()
    assert c.get(base + "/projects").status_code == 404


def test_viewer_cannot_write_or_read_billing(tenant):
    Membership.objects.filter(user=tenant["user"]).update(role="viewer")
    c, base = tenant["client"], tenant["base"]
    assert c.get(base + "/projects").status_code == 200
    assert (
        c.post(base + "/projects", {"name": "New", "site_url": "https://example.com"}).status_code
        == 403
    )
    assert c.get(base + "/billing").status_code == 403


def test_create_workspace_and_project_validation(tenant):
    c = tenant["client"]
    assert c.post("/api/workspaces", {"name": "New studio"}).status_code == 201
    assert (
        c.post(
            tenant["base"] + "/projects", {"name": "New", "site_url": "http://localhost"}
        ).status_code
        == 400
    )
    response = c.post(
        tenant["base"] + "/projects", {"name": "New", "site_url": "https://EXAMPLE.COM"}
    )
    assert response.status_code == 201
    assert response.json()["site_url"] == "https://example.com/"


def test_audit_request_idempotency_and_scoping(tenant):
    url = f"{tenant['base']}/projects/{tenant['project'].id}/runs"
    c = tenant["client"]
    assert c.post(url, {"source": "fixture"}).status_code == 400
    with patch("core.views.publish"), pytest.raises(RuntimeError):
        # A failing transaction rolls back both the job and activity event.
        from django.db import transaction

        with transaction.atomic():
            assert c.post(url, {"source": "fixture"}, HTTP_IDEMPOTENCY_KEY="one").status_code == 202
            raise RuntimeError("rollback")
    assert AuditRun.objects.count() == 0
    with patch("core.views.publish"):
        first = c.post(url, {"source": "fixture"}, HTTP_IDEMPOTENCY_KEY="one")
        replay = c.post(url, {"source": "fixture"}, HTTP_IDEMPOTENCY_KEY="one")
        conflict = c.post(url, {"source": "live"}, HTTP_IDEMPOTENCY_KEY="one")
    assert first.status_code == 202
    assert replay.status_code == 200 and replay.json()["id"] == first.json()["id"]
    assert conflict.status_code == 409
    assert len(c.get(url).json()) == 1
    assert (
        c.get(url.replace(str(tenant["workspace"].id), str(tenant["foreign"].id))).status_code
        == 404
    )


def test_findings_assignment_version_and_activity(tenant, run):
    execute_audit(str(run.id))
    c, base = tenant["client"], tenant["base"]
    with CaptureQueriesContext(connection) as queries:
        findings = c.get(f"{base}/runs/{run.id}/findings").json()
    assert len(findings) == 3
    assert len(queries) == 3  # Membership, scoped run, findings joined to actions; no N+1.
    url = f"{base}/findings/{findings[0]['id']}/action"
    assert (
        c.patch(
            url,
            {"state": "resolved", "version": 1, "assignee_id": tenant["other"].id},
            format="json",
        ).status_code
        == 400
    )
    response = c.patch(
        url, {"state": "in_progress", "version": 1, "assignee_id": tenant["user"].id}, format="json"
    )
    assert response.status_code == 200 and response.json()["version"] == 2
    assert Action.objects.get(finding_id=findings[0]["id"]).assignee == tenant["user"]
    assert c.patch(url, {"state": "resolved", "version": 1}, format="json").status_code == 409
    assert c.patch(url, {"state": "unknown", "version": 2}, format="json").status_code == 400
    assert c.get(base + "/activity").json()[0]["kind"] == "action.in_progress"
    assert AuditEvent.objects.filter(workspace=tenant["foreign"]).count() == 0
    assert c.get(base + "/billing").json() == []


def test_metrics_health_and_body_limit(settings):
    c = APIClient()
    assert c.get("/api/health/live").content == b"ok"
    response = c.get("/api/health/ready")
    assert response.status_code == 200 and response["X-Request-ID"]
    assert response["Cache-Control"] == "no-store"
    assert response["X-Frame-Options"] == "DENY"
    assert c.get("/api/metrics").status_code == 403
    settings.METRICS_TOKEN = "test-metrics-token"
    assert c.get("/api/metrics", HTTP_AUTHORIZATION="Bearer test-metrics-token").status_code == 200
    with patch("core.views.connection.cursor", side_effect=RuntimeError):
        assert c.get("/api/health/ready").status_code == 503
    response = c.generic(
        "POST", "/api/auth/login", b"x" * 1_048_577, content_type="application/json"
    )
    assert response.status_code == 413
