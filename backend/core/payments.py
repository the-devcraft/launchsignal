import hashlib

from django.db import connection, transaction
from rest_framework.exceptions import ValidationError

from core.api_errors import Conflict
from core.models import AuditEvent, BillingCustomer, BillingEvent, BillingInvoice


@transaction.atomic
def apply_event(event, raw_body):
    if not isinstance(event, dict):
        raise ValidationError("Invalid event object")
    event_id, kind, created = event.get("id"), event.get("type"), event.get("created")
    if kind not in ("invoice.paid", "invoice.payment_failed", "invoice.voided"):
        return {"result": "unsupported_event"}
    data = event.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("object"), dict):
        raise ValidationError("Invalid invoice object")
    invoice = data["object"]
    customer_id, invoice_id = invoice.get("customer"), invoice.get("id")
    if not all(
        isinstance(x, str) and 1 <= len(x) <= 100 for x in (event_id, customer_id, invoice_id)
    ):
        raise ValidationError("Invalid provider references")
    if type(created) is not int or created < 0:
        raise ValidationError("Invalid event time")
    due, paid, currency = (
        invoice.get("amount_due"),
        invoice.get("amount_paid"),
        invoice.get("currency"),
    )
    if any(type(x) is not int or not 0 <= x <= 10**12 for x in (due, paid)):
        raise ValidationError("Amounts must be bounded integer minor units")
    if currency not in ("usd", "eur", "gbp"):
        raise ValidationError("Unsupported currency")
    # Lock provider references before reading state, including absent invoice rows.
    # Sorted transaction-scoped locks avoid deadlocks and cross-customer insert races.
    with connection.cursor() as cursor:
        for ref in sorted((f"event:{event_id}", f"invoice:{invoice_id}")):
            key = int.from_bytes(hashlib.sha256(ref.encode()).digest()[:8], signed=True)
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])
    # The signed provider customer mapping is authoritative; metadata.workspace_id is ignored.
    mapping = BillingCustomer.objects.select_for_update().filter(provider_id=customer_id).first()
    if mapping is None:
        raise ValidationError("Unknown billing customer")
    fingerprint = hashlib.sha256(raw_body).hexdigest()
    prior = BillingEvent.objects.filter(provider_id=event_id).first()
    if prior:
        if prior.fingerprint != fingerprint or prior.workspace_id != mapping.workspace_id:
            raise Conflict("Provider event ID has conflicting content")
        return {"result": "duplicate"}
    existing = BillingInvoice.objects.select_for_update().filter(provider_id=invoice_id).first()
    if existing and existing.workspace_id != mapping.workspace_id:
        raise Conflict("Invoice customer mapping conflict")
    status = {"invoice.paid": "paid", "invoice.payment_failed": "open", "invoice.voided": "void"}[
        kind
    ]
    apply = existing is None or created > existing.provider_created
    if existing and existing.status in ("paid", "void") and status != existing.status:
        apply = False
    if apply:
        BillingInvoice.objects.update_or_create(
            provider_id=invoice_id,
            defaults={
                "workspace": mapping.workspace,
                "currency": currency,
                "amount_due": due,
                "amount_paid": paid,
                "status": status,
                "provider_created": created,
            },
        )
    BillingEvent.objects.create(
        provider_id=event_id,
        fingerprint=fingerprint,
        workspace=mapping.workspace,
        kind=kind,
        applied=apply,
    )
    AuditEvent.objects.create(
        workspace=mapping.workspace, kind="billing.event_received", object_id=event_id
    )
    return {"result": "applied" if apply else "out_of_order"}
