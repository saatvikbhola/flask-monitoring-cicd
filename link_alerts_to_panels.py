import json
import urllib.request
import base64

GRAFANA_URL = "http://localhost:3000"
DS_UID = "ag3v9noldmzuoc"
DASH_UID = "flask-weather-space-v2"
AUTH = base64.b64encode(b"admin:admin").decode("ascii")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {AUTH}",
    "X-Disable-Provenance": "true"
}

folder_UID = "flask-alerts-folder"
try:
    req = urllib.request.Request(
        f"{GRAFANA_URL}/api/folders",
        data=json.dumps({"title": "Production Server Alerts", "uid": folder_UID}).encode("utf-8"),
        headers=HEADERS
    )
    urllib.request.urlopen(req)
except Exception:
    pass

# Delete existing rules
req = urllib.request.Request(f"{GRAFANA_URL}/api/v1/provisioning/alert-rules", headers=HEADERS)
with urllib.request.urlopen(req) as resp:
    existing = json.loads(resp.read().decode("utf-8"))
    for r in existing:
        if r.get("folderUID") == folder_UID:
            del_req = urllib.request.Request(
                f"{GRAFANA_URL}/api/v1/provisioning/alert-rules/{r['uid']}",
                headers=HEADERS,
                method="DELETE"
            )
            urllib.request.urlopen(del_req)

# Production Golden Signals Alert Rules
# Panel 1: Service Health
# Panel 2: Host CPU
# Panel 3: Host RAM
# Panel 6: HTTP Traffic & Error Rate
# Panel 8: API Latency
prod_alerts = [
    (
        "ServiceDown",
        'up{job="flask_app"} == 0',
        "Flask application container is unreachable or crashed",
        "1m",
        "critical",
        "1"
    ),
    (
        "HighServerErrorRate",
        '(sum(rate(http_requests_total{http_status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))) * 100 > 5',
        "HTTP 5xx Server Error Ratio exceeds 5% of all traffic",
        "2m",
        "critical",
        "6"
    ),
    (
        "DegradedApiLatency",
        'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 1.0',
        "API p95 latency degraded beyond 1.0s",
        "3m",
        "warning",
        "8"
    ),
    (
        "HostCpuSaturation",
        '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85',
        "Host CPU utilization critical (> 85%)",
        "5m",
        "warning",
        "2"
    ),
    (
        "HostMemorySaturation",
        '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90',
        "Host Memory utilization critical (> 90%)",
        "5m",
        "warning",
        "3"
    ),
    (
        "UpstreamGatewayOutage",
        'sum(rate(http_requests_total{http_status=~"502|504"}[5m])) > 0.05',
        "Third-party external API (Open-Meteo) timeout or 502/504 gateway outage",
        "2m",
        "warning",
        "6"
    )
]

for title, expr, summary, for_duration, severity, panel_id in prod_alerts:
    payload = {
        "title": title,
        "condition": "C",
        "data": [
            {
                "refId": "A",
                "datasourceUid": DS_UID,
                "relativeTimeRange": {"from": 300, "to": 0},
                "model": {
                    "editorMode": "code",
                    "expr": expr,
                    "intervalMs": 1000,
                    "maxDataPoints": 43200,
                    "refId": "A",
                    "instant": True
                }
            },
            {
                "refId": "C",
                "datasourceUid": "__expr__",
                "relativeTimeRange": {"from": 300, "to": 0},
                "model": {
                    "conditions": [{
                        "evaluator": {"params": [0], "type": "gt"},
                        "operator": {"type": "and"},
                        "query": {"params": ["A"]},
                        "reducer": {"params": [], "type": "last"},
                        "type": "query"
                    }],
                    "datasource": {"type": "__expr__", "uid": "__expr__"},
                    "refId": "C",
                    "type": "classic_conditions"
                }
            }
        ],
        "folderUID": folder_UID,
        "ruleGroup": "production-alerts",
        "for": for_duration,
        "labels": {"severity": severity},
        "annotations": {
            "summary": summary,
            "__dashboardUid__": DASH_UID,
            "__panelId__": panel_id
        },
        "noDataState": "OK",
        "execErrState": "Error"
    }
    req = urllib.request.Request(
        f"{GRAFANA_URL}/api/v1/provisioning/alert-rules",
        data=json.dumps(payload).encode("utf-8"),
        headers=HEADERS
    )
    with urllib.request.urlopen(req) as resp:
        print(f"Provisioned production alert '{title}' linked to Panel {panel_id}")
