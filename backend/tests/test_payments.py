import copy
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from core.api_errors import Conflict
from core.models import BillingCustomer, BillingEvent, BillingInvoice
from core.payments import apply_event
from django.db import close_old_connections
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def apply(event):
    return apply_event(event, json.dumps(event, sort_keys=True).encode())


def test_replay_conflict_out_of_order_and_terminal_state(tenant, event):
    assert apply(event) == {"result": "applied"}
    assert apply(event) == {"result": "duplicate"}
    modified = copy.deepcopy(event)
    modified["data"]["object"]["amount_paid"] = 100
    with pytest.raises(Conflict):
        apply(modified)
    modified["id"], modified["created"] = "evt_two", 99
    assert apply(modified) == {"result": "out_of_order"}
    modified["id"], modified["created"], modified["type"] = (
        "evt_three",
        101,
        "invoice.payment_failed",
    )
    assert apply(modified) == {"result": "out_of_order"}
    assert BillingInvoice.objects.get().amount_paid == 14900
    assert BillingEvent.objects.count() == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount_paid", -1),
        ("amount_due", True),
        ("amount_paid", 1.2),
        ("amount_due", 10**13),
        ("currency", "xyz"),
        ("customer", "missing"),
        ("id", None),
    ],
)
def test_invalid_invoice_is_atomic(tenant, event, field, value):
    event["data"]["object"][field] = value
    with pytest.raises(ValidationError):
        apply(event)
    assert not BillingEvent.objects.exists() and not BillingInvoice.objects.exists()


def test_shape_validation_and_customer_authority(tenant, event):
    assert apply_event({"type": "unhandled"}, b"{}") == {"result": "unsupported_event"}
    for bad in [[], {"type": "invoice.paid", "data": None}, {**event, "created": True}]:
        with pytest.raises(ValidationError):
            apply_event(bad, b"{}")
    event["data"]["object"]["metadata"] = {"workspace_id": str(tenant["foreign"].id)}
    apply(event)
    assert BillingInvoice.objects.get().workspace == tenant["workspace"]
    BillingCustomer.objects.create(workspace=tenant["foreign"], provider_id="cus_other")
    event["id"] = "evt_foreign"
    event["data"]["object"]["customer"] = "cus_other"
    with pytest.raises(Conflict):
        apply(event)


def test_real_stripe_signature_and_clock_window(settings, tenant, event):
    client = APIClient(enforce_csrf_checks=True)
    url = "/api/webhooks/stripe"
    assert client.post(url, {}, format="json").status_code == 503
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test_fixture_only"
    body = json.dumps(event).encode()
    assert client.post(url, body, content_type="application/json").status_code == 400
    for age, status in [(600, 400), (0, 200)]:
        stamp = int(time.time()) - age
        digest = hmac.new(
            settings.STRIPE_WEBHOOK_SECRET.encode(),
            str(stamp).encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        response = client.post(
            url,
            body,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=f"t={stamp},v1={digest}",
        )
        assert response.status_code == status
    assert BillingInvoice.objects.get().status == "paid"
    assert client.post(url, b"x" * 65_537, content_type="application/json").status_code == 400


@pytest.mark.django_db(transaction=True)
def test_concurrent_delivery_is_exactly_once(tenant, event):
    def deliver(_):
        close_old_connections()
        try:
            return apply(event)["result"]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(deliver, range(2))) == ["applied", "duplicate"]
    assert BillingEvent.objects.count() == BillingInvoice.objects.count() == 1
