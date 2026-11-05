import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from celery.contrib.testing.worker import start_worker
from config.celery import app
from core.models import AuditRun
from core.tasks import execute_audit
from django.db import close_old_connections
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db(transaction=True)


def test_real_celery_worker_commits_results(run):
    app.loader.import_default_modules()
    with start_worker(app, pool="solo", perform_ping_check=False, loglevel="WARNING"):
        execute_audit.delay(str(run.id))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            run.refresh_from_db()
            if run.status == "succeeded":
                break
            time.sleep(0.1)
        assert run.status == "succeeded"
        assert run.findings.count() == 3


def test_simultaneous_audit_requests_create_one_job(tenant):
    def request(_):
        close_old_connections()
        client = APIClient()
        client.force_authenticate(tenant["user"])
        try:
            return client.post(
                f"{tenant['base']}/projects/{tenant['project'].id}/runs",
                {"source": "fixture"},
                HTTP_IDEMPOTENCY_KEY="concurrent",
            ).status_code
        finally:
            close_old_connections()

    from unittest.mock import patch

    with patch("core.views.publish"), ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(request, range(2))) == [200, 202]
    assert AuditRun.objects.count() == 1
