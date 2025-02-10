FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-runtime.lock ./requirements-runtime.lock
RUN pip install --no-cache-dir -r requirements-runtime.lock && useradd --uid 10001 --create-home app \
    && mkdir -p /var/log/launchsignal && chown app:app /var/log/launchsignal
COPY backend/ ./
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "35", "--access-logfile", "/dev/null"]
