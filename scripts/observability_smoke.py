"""Fail CI if the optional local telemetry pipeline is not ingesting real data."""
import subprocess
import time

PROBE = r'''
import json, urllib.request, urllib.parse
def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.load(r)
metrics = get('http://mimir:9009/prometheus/api/v1/query?query=sum(launchsignal_jobs)')
assert metrics['data']['result'], 'No LaunchSignal metrics in Mimir'
query = urllib.parse.urlencode({'query': '{job="launchsignal"} |= "request.complete"', 'limit': 1})
logs = get('http://loki:3100/loki/api/v1/query_range?' + query)
assert logs['data']['result'], 'No application logs in Loki'
traces = get('http://tempo:3200/api/search?' + urllib.parse.urlencode({'q': '{ resource.service.name = "launchsignal-api" }'}))
assert traces['traces'], 'No API traces in Tempo'
print('Verified: metrics in Mimir, logs in Loki, traces in Tempo')
'''

for attempt in range(24):
    result = subprocess.run(["docker", "compose", "exec", "-T", "api", "python", "-c", PROBE],
                            capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout.strip())
        break
    if attempt == 23:
        raise SystemExit(result.stderr)
    time.sleep(5)
