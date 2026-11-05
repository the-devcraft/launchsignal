import json
from pathlib import Path

import pytest
from core.api_errors import Conflict
from core.auditing import analyze
from core.models import BillingEvent, BillingInvoice
from core.payments import apply_event
from core.telemetry import HTTP_REQUESTS
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient


def apply(event):
    return apply_event(event, json.dumps(event, sort_keys=True).encode())


@pytest.mark.parametrize("heading", ["<h1></h1>", "<h1>  </h1>", "<h1><span></span></h1>"])
def test_empty_primary_heading_is_a_finding(heading):
    healthy = (Path(__file__).parents[1] / "core/fixtures/healthy.html").read_text()
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(healthy, "html.parser")
    soup.h1.replace_with(BeautifulSoup(heading, "html.parser"))
    score, findings = analyze(str(soup))
    assert score == 80
    assert [item["code"] for item in findings] == ["heading"]


@pytest.mark.parametrize(
    "href", ["/relative", "javascript:alert(1)", "https://", "http://example.com/"]
)
def test_canonical_must_be_an_absolute_https_url(href):
    healthy = (Path(__file__).parents[1] / "core/fixtures/healthy.html").read_text()
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(healthy, "html.parser")
    soup.find("link", rel="canonical")["href"] = href
    score, findings = analyze(str(soup))
    assert score == 85
    assert [item["code"] for item in findings] == ["canonical"]


@pytest.mark.django_db
def test_provider_time_outside_database_range_is_validation_error(tenant, event):
    event["created"] = 2**63
    with pytest.raises(ValidationError):
        apply(event)
    assert not BillingEvent.objects.exists() and not BillingInvoice.objects.exists()


@pytest.mark.django_db
def test_an_existing_invoice_cannot_silently_change_currency(tenant, event):
    apply(event)
    event["id"], event["created"] = "evt_currency_change", 101
    event["data"]["object"]["currency"] = "eur"
    with pytest.raises(Conflict):
        apply(event)
    assert BillingInvoice.objects.get().currency == "usd"
    assert BillingEvent.objects.count() == 1


def test_untrusted_http_methods_cannot_create_unbounded_metric_series():
    client = APIClient()
    for verb in ["CUSTOMVERBONE", "CUSTOMVERBTWO"]:
        assert client.generic(verb, "/api/health/live").status_code == 200
    samples = [sample for metric in HTTP_REQUESTS.collect() for sample in metric.samples]
    labels = {sample.labels["method"] for sample in samples}
    assert "CUSTOMVERBONE" not in labels and "CUSTOMVERBTWO" not in labels
    assert "OTHER" in labels
