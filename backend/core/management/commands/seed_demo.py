import hashlib
import os
import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import AuditRun, BillingCustomer, Membership, Project, Workspace
from core.payments import apply_event
from core.tasks import execute_audit


class Command(BaseCommand):
    help = "Create local fixture data; never connects to websites or a payment provider"

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.getenv("DEMO_PASSWORD", "")
        if len(password) < 12:
            raise CommandError(
                "Set DEMO_PASSWORD to at least 12 characters; no default is supplied"
            )
        user, created = get_user_model().objects.get_or_create(
            username="demo@launchsignal.test",
            defaults={"first_name": "Alex", "last_name": "Morgan"},
        )
        if not created:
            self.stdout.write("Demo already exists; existing data and password were preserved")
            return
        user.set_password(password)
        user.save()
        workspace = Workspace.objects.create(name="Orbit Studio")
        Membership.objects.create(workspace=workspace, user=user, role="owner")
        secondary = Workspace.objects.create(name="Personal sandbox")
        Membership.objects.create(workspace=secondary, user=user, role="owner")
        for name, url, fixture in [
            ("Orbit Studio", "https://example.com/", "baseline"),
            ("Northline Journal", "https://example.org/", "healthy"),
            ("Fieldwork Supply", "https://example.net/", "baseline"),
        ]:
            project = Project.objects.create(workspace=workspace, name=name, site_url=url)
            run = AuditRun.objects.create(
                project=project,
                requested_by=user,
                request_key="seed",
                fingerprint=hashlib.sha256(b"seed").hexdigest(),
                source="fixture",
                fixture=fixture,
            )
            execute_audit(str(run.id))
        BillingCustomer.objects.create(workspace=workspace, provider_id="cus_launchsignal_fixture")
        with transaction.atomic():
            for index, (due, paid, kind) in enumerate(
                [(14900, 14900, "invoice.paid"), (14900, 0, "invoice.payment_failed")]
            ):
                event = {
                    "id": f"evt_fixture_{index}",
                    "type": kind,
                    "created": int(time.time()) + index,
                    "data": {
                        "object": {
                            "id": f"in_fixture_{index}",
                            "customer": "cus_launchsignal_fixture",
                            "currency": "usd",
                            "amount_due": due,
                            "amount_paid": paid,
                        }
                    },
                }
                import json

                raw = json.dumps(event).encode()
                apply_event(event, raw)
        self.stdout.write("Demo ready: demo@launchsignal.test (password from DEMO_PASSWORD)")
