import pytest
from core.models import Membership
from core.tasks import execute_audit

pytestmark = pytest.mark.django_db


def test_nested_resources_cannot_cross_two_authorized_workspaces(tenant, run):
    # The user belongs to both tenants. The nested ID must still match its parent.
    Membership.objects.create(workspace=tenant["foreign"], user=tenant["user"], role="editor")
    execute_audit(str(run.id))
    c = tenant["client"]
    foreign = f"/api/workspaces/{tenant['foreign'].id}"
    assert c.get(f"{foreign}/projects/{tenant['project'].id}/runs").status_code == 404
    assert c.get(f"{foreign}/runs/{run.id}/findings").status_code == 404
    finding = run.findings.first()
    assert (
        c.patch(
            f"{foreign}/findings/{finding.id}/action",
            {"state": "resolved", "version": 1},
            format="json",
        ).status_code
        == 404
    )
    assert c.get(foreign + "/billing").status_code == 403
