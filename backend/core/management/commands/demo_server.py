from celery.contrib.testing.worker import start_worker
from config.celery import app
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Local-only API plus a real in-process Celery worker using the memory broker"

    def handle(self, *args, **options):
        if not settings.DEBUG or settings.CELERY_BROKER_URL != "memory://":
            raise CommandError("demo_server requires DEBUG and CELERY_BROKER_URL=memory://")
        app.loader.import_default_modules()
        with start_worker(app, pool="solo", perform_ping_check=False, loglevel="INFO"):
            call_command("runserver", "127.0.0.1:8000", use_reloader=False)
