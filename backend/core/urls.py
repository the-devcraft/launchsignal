from django.urls import path

from core import views

urlpatterns = [
    path("auth/session", views.SessionView.as_view()),
    path("auth/login", views.LoginView.as_view()),
    path("auth/logout", views.LogoutView.as_view()),
    path("workspaces", views.WorkspacesView.as_view()),
    path("workspaces/<uuid:workspace_id>/members", views.MembersView.as_view()),
    path("workspaces/<uuid:workspace_id>/projects", views.ProjectsView.as_view()),
    path(
        "workspaces/<uuid:workspace_id>/projects/<uuid:project_id>/runs", views.RunsView.as_view()
    ),
    path(
        "workspaces/<uuid:workspace_id>/runs/<uuid:run_id>/findings", views.FindingsView.as_view()
    ),
    path(
        "workspaces/<uuid:workspace_id>/findings/<uuid:finding_id>/action",
        views.ActionView.as_view(),
    ),
    path("workspaces/<uuid:workspace_id>/activity", views.ActivityView.as_view()),
    path("workspaces/<uuid:workspace_id>/billing", views.BillingView.as_view()),
    path("webhooks/stripe", views.StripeWebhook.as_view()),
    path("health/live", views.liveness),
    path("health/ready", views.readiness),
    path("metrics", views.metrics),
]
