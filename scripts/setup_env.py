"""Generate local-only secrets once without printing them or overwriting an existing file."""
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
values = (root / ".env.example").read_text().splitlines()
required = {"POSTGRES_PASSWORD", "DJANGO_SECRET_KEY", "DEMO_PASSWORD", "METRICS_TOKEN", "GRAFANA_PASSWORD"}
lines = []
for line in values:
    name = line.partition("=")[0]
    lines.append(f"{name}={secrets.token_urlsafe(32)}" if name in required else line)
try:
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit("Existing .env preserved. Edit it directly if configuration changes are needed.") from None
with os.fdopen(descriptor, "w") as stream:
    stream.write("\n".join(lines)+"\n")
print("Created local .env. Read DEMO_PASSWORD there for demo login; do not commit this file.")
