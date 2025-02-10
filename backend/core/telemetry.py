import json
import logging
import os
import time
import uuid

from django.http import JsonResponse
from opentelemetry import trace
from prometheus_client import Counter, Gauge, Histogram


class BodyLimit:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ("POST", "PUT", "PATCH"):
            from django.core.exceptions import RequestDataTooBig

            try:
                _ = request.body
            except RequestDataTooBig:
                return JsonResponse({"detail": "Request body too large"}, status=413)
        return self.get_response(request)


HTTP_REQUESTS = Counter(
    "launchsignal_http_requests", "HTTP responses", ["route", "method", "status"]
)
HTTP_LATENCY = Histogram("launchsignal_http_seconds", "Request duration", ["route"])
AUDITS = Counter("launchsignal_audit_outcomes", "Audit attempts", ["outcome"])
AUDIT_LATENCY = Histogram("launchsignal_audit_seconds", "Worker processing duration")
JOBS = Gauge("launchsignal_jobs", "Durable audit runs by state", ["status"])


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {"level": record.levelname, "logger": record.name, "message": record.getMessage()}
        for field in ("request_id", "trace_id", "route", "status", "duration_ms", "run_id"):
            if hasattr(record, field):
                data[field] = getattr(record, field)
        return json.dumps(data)


class RequestMetrics:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        started = time.perf_counter()
        response = self.get_response(request)
        route = str(request.resolver_match.route) if request.resolver_match else "unmatched"
        elapsed = time.perf_counter() - started
        HTTP_REQUESTS.labels(route, request.method, response.status_code).inc()
        HTTP_LATENCY.labels(route).observe(elapsed)
        response["X-Request-ID"] = request.request_id
        response["Cache-Control"] = "no-store"
        span = trace.get_current_span().get_span_context()
        logging.getLogger("launchsignal.http").info(
            "request.complete",
            extra={
                "request_id": request.request_id,
                "route": route,
                "status": response.status_code,
                "duration_ms": round(elapsed * 1000, 2),
                "trace_id": format(span.trace_id, "032x"),
            },
        )
        return response


def configure_tracing():
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": os.getenv("OTEL_SERVICE_NAME", "launchsignal-api")}
        )
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    DjangoInstrumentor().instrument()
    CeleryInstrumentor().instrument()
