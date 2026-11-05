import os

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            from core.telemetry import configure_tracing

            configure_tracing()
