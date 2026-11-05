import pytest
from core.models import AuditRun, BillingCustomer, Membership, Project, Workspace
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def isolated_cache(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()


@pytest.fixture
def tenant(db):
    user = get_user_model().objects.create_user("owner", password="test-password-123")
    other = get_user_model().objects.create_user("outsider", password="test-password-123")
    workspace = Workspace.objects.create(name="Studio")
    foreign = Workspace.objects.create(name="Separate company")
    Membership.objects.create(workspace=workspace, user=user, role="owner")
    Membership.objects.create(workspace=foreign, user=other, role="owner")
    project = Project.objects.create(
        workspace=workspace, name="Site", site_url="https://example.com/"
    )
    BillingCustomer.objects.create(workspace=workspace, provider_id="cus_test")
    client = APIClient()
    client.force_authenticate(user)
    return {
        "user": user,
        "other": other,
        "workspace": workspace,
        "foreign": foreign,
        "project": project,
        "client": client,
        "base": f"/api/workspaces/{workspace.id}",
    }


@pytest.fixture
def run(tenant):
    return AuditRun.objects.create(
        project=tenant["project"],
        requested_by=tenant["user"],
        request_key="test",
        fingerprint="fixture",
        source="fixture",
    )


@pytest.fixture
def event():
    return {
        "id": "evt_one",
        "type": "invoice.paid",
        "created": 100,
        "data": {
            "object": {
                "id": "in_one",
                "customer": "cus_test",
                "currency": "usd",
                "amount_due": 14900,
                "amount_paid": 14900,
            }
        },
    }
