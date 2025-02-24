"""Sequential authenticated API baseline; not a load test or production capacity claim."""
import argparse
import http.cookiejar
import json
import os
import platform
import statistics
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:3000")
parser.add_argument("--samples", type=int, default=100)
args = parser.parse_args()
if not 10 <= args.samples <= 1000:
    parser.error("samples must be between 10 and 1000")
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(path, data=None, csrf=""):
    req = urllib.request.Request(args.url + "/api/" + path,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json", "X-CSRFToken": csrf, "Origin": args.url})
    with opener.open(req, timeout=10) as response:
        return json.load(response)


token = request("auth/session")["csrf_token"]
request("auth/login", {"username": "demo@launchsignal.test", "password": os.environ["DEMO_PASSWORD"]}, token)
workspace = next(x for x in request("workspaces") if x["workspace__name"] == "Orbit Studio")
project = next(x for x in request(f'workspaces/{workspace["workspace_id"]}/projects') if x["name"] == "Orbit Studio")
run = request(f'workspaces/{workspace["workspace_id"]}/projects/{project["id"]}/runs')[0]
endpoint = f'workspaces/{workspace["workspace_id"]}/runs/{run["id"]}/findings'
for _ in range(10):
    request(endpoint)
times = []
for _ in range(args.samples):
    started = time.perf_counter()
    request(endpoint)
    times.append((time.perf_counter() - started) * 1000)
ordered = sorted(times)
print(json.dumps({"workload": "session-authenticated seeded findings read via Next proxy",
    "concurrency": 1, "warmup_requests": 10, "samples": args.samples,
    "client_os": platform.system(), "python": platform.python_version(),
    "p50_ms": round(statistics.median(times),2),
    "p95_ms": round(ordered[int(.95*len(ordered))-1],2), "max_ms": round(max(times),2)}, indent=2))
