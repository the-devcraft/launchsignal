import os
from pathlib import Path

import dj_database_url
import sentry_sdk

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,api").split(",")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "core.apps.CoreConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.telemetry.BodyLimit",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.telemetry.RequestMetrics",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
ROOT_URLCONF = "config.urls"
DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=0)}
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise RuntimeError("LaunchSignal requires PostgreSQL")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 30,
    "EXCEPTION_HANDLER": "core.api_errors.handler",
}
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_NAME = "launchsignal_session"
CSRF_COOKIE_NAME = "launchsignal_csrf"
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = os.getenv(
    "APP_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_048_576
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = None
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BEAT_SCHEDULE = {"dispatch-audits": {"task": "core.tasks.dispatch_pending", "schedule": 15}}
AUDIT_ALLOWED_HOSTS = set(filter(None, os.getenv("AUDIT_ALLOWED_HOSTS", "").split(",")))
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")
CACHES = {
    "default": (
        {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.environ["CACHE_URL"],
        }
        if os.getenv("CACHE_URL")
        else {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    )
}
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"login": "10/minute"}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "core.telemetry.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
if os.getenv("LOG_DIR"):
    LOGGING["handlers"]["file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "formatter": "json",
        "filename": str(
            Path(os.environ["LOG_DIR"]) / f"{os.getenv('OTEL_SERVICE_NAME', 'api')}.log"
        ),
        "maxBytes": 5_000_000,
        "backupCount": 2,
    }
    LOGGING["root"]["handlers"].append("file")
if os.getenv("SENTRY_DSN"):
    # Explicit opt-in; local fixture mode sends no telemetry to an external service.
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=0.1,
        environment=os.getenv("APP_ENV", "development"),
    )
