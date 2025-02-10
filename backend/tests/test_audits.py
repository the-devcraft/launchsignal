import socket
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from core.auditing import (
    FetchPolicyError,
    PinnedHTTPSConnection,
    analyze,
    fetch_html,
    normalized_url,
)
from core.models import AuditRun, Finding
from core.tasks import dispatch_pending, execute_audit, publish
from django.utils import timezone


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com:444",
        "https://example.com/#private",
        "https://",
        "https://[bad",
    ],
)
def test_invalid_url(url):
    with pytest.raises(FetchPolicyError):
        normalized_url(url)


def test_parser_explainable_rules():
    fixture = Path(__file__).parents[1] / "core/fixtures"
    assert analyze((fixture / "healthy.html").read_text()) == (100, [])
    score, findings = analyze((fixture / "baseline.html").read_text())
    assert score == 40 and {x["code"] for x in findings} == {
        "description",
        "canonical",
        "image_alt",
    }
    assert analyze("<title>" + "x" * 71 + "</title><h1>A</h1><h1>B</h1>")[0] == 25
    with pytest.raises(FetchPolicyError, match="page_too_large"):
        analyze("x" * 524_289)


def test_fetch_ssrf_and_pinned_tls(settings):
    settings.AUDIT_ALLOWED_HOSTS = {"example.com"}
    with pytest.raises(FetchPolicyError, match="allowlisted"):
        fetch_html("https://unapproved.example/")
    for address in ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"]:
        with patch(
            "core.auditing.socket.getaddrinfo", return_value=[(0, 0, 0, "", (address, 443))]
        ):
            with pytest.raises(FetchPolicyError, match="non_public"):
                fetch_html("https://example.com/")
    conn = PinnedHTTPSConnection("example.com", "93.184.216.34")
    conn._context = MagicMock()
    with patch("core.auditing.socket.create_connection") as create:
        conn.connect()
        create.assert_called_once_with(("93.184.216.34", 443), timeout=8)
        conn._context.wrap_socket.assert_called_once_with(
            create.return_value, server_hostname="example.com"
        )
        conn._context.wrap_socket.side_effect = OSError
        with pytest.raises(OSError):
            conn.connect()
        assert create.return_value.close.called


@pytest.mark.parametrize(
    "status,content_type,encoding,body,error",
    [
        (302, "text/html", "identity", b"", "redirect"),
        (503, "text/html", "identity", b"", "upstream"),
        (404, "text/html", "identity", b"", "rejected"),
        (200, "image/png", "identity", b"", "html_required"),
        (200, "text/html", "gzip", b"", "encoded"),
        (200, "text/html", "identity", b"x" * 524_289, "too_large"),
        (200, "text/html; charset=utf-8", "identity", b"<h1>Works</h1>", None),
    ],
)
def test_fetch_http_boundaries(settings, status, content_type, encoding, body, error):
    settings.AUDIT_ALLOWED_HOSTS = {"example.com"}
    response = MagicMock(status=status)
    response.getheader.side_effect = lambda key, default: {
        "Content-Type": content_type,
        "Content-Encoding": encoding,
    }.get(key, default)
    response.read.return_value = body
    with (
        patch(
            "core.auditing.socket.getaddrinfo",
            return_value=[(socket.AF_INET, 0, 0, "", ("93.184.216.34", 443))],
        ),
        patch("core.auditing.PinnedHTTPSConnection") as cls,
    ):
        conn = cls.return_value
        conn.getresponse.return_value = response
        if error:
            with pytest.raises((FetchPolicyError, OSError), match=error):
                fetch_html("https://example.com/page?q=1")
        else:
            assert fetch_html("https://example.com/page?q=1") == body.decode()
            assert conn.request.call_args.args[:2] == ("GET", "/page?q=1")
        assert conn.close.called


@pytest.mark.django_db
def test_worker_idempotency_and_active_lease(run):
    assert execute_audit(str(run.id)) == "succeeded"
    assert execute_audit(str(run.id)) == "ignored"
    run.refresh_from_db()
    assert run.score == 40 and run.attempts == 1 and Finding.objects.count() == 3
    assert execute_audit(str(uuid.uuid4())) == "ignored"


@pytest.mark.django_db
def test_worker_retry_budget_and_dispatch(run):
    run.source = "live"
    run.save()
    with patch("core.tasks.fetch_html", side_effect=OSError):
        for attempt in range(3):
            assert execute_audit(str(run.id)) == ("pending" if attempt < 2 else "failed")
            if attempt < 2:
                assert execute_audit(str(run.id)) == "delayed"
                AuditRun.objects.filter(pk=run.pk).update(
                    next_attempt_at=timezone.now() - timedelta(seconds=1)
                )
    assert Finding.objects.count() == 0
    run.status, run.attempts, run.lease_until = "running", 3, timezone.now() - timedelta(seconds=1)
    run.next_attempt_at = None
    run.save()
    with patch("core.tasks.publish") as enqueue:
        dispatch_pending()
        enqueue.assert_called_once_with(run.id)
    assert execute_audit(str(run.id)) == "exhausted"


@pytest.mark.django_db
def test_fencing_discards_stale_worker(run):
    def steal(_):
        AuditRun.objects.filter(pk=run.pk).update(lease_token=uuid.uuid4())
        return (100, [])

    with patch("core.tasks.analyze", side_effect=steal):
        assert execute_audit(str(run.id)) == "stale"
    assert Finding.objects.count() == 0
    run.refresh_from_db()
    assert execute_audit(str(run.id)) == "leased"


@pytest.mark.django_db
def test_policy_failure_and_publication_recovery(run):
    run.fixture = "../../secret"
    run.save()
    assert execute_audit(str(run.id)) == "failed"
    with patch("core.tasks.execute_audit.delay", side_effect=ConnectionError):
        publish(run.id)  # Broker outage does not roll back the durable request.
