import json
import urllib.request
import base64

DS_UID = "ag3v9noldmzuoc"
GRAFANA_URL = "http://localhost:3000"
AUTH = base64.b64encode(b"admin:admin").decode("ascii")

dashboard = {
    "dashboard": {
        "title": "Production Server & API Monitoring",
        "uid": "flask-weather-space-v2",
        "timezone": "browser",
        "schemaVersion": 38,
        "refresh": "5s",
        "time": {"from": "now-15m", "to": "now"},
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "enable": True,
                    "hide": False,
                    "iconColor": "rgba(255, 96, 96, 1)",
                    "name": "Annotations & Alerts",
                    "type": "dashboard"
                }
            ]
        },
        "panels": [
            # ROW 1: 4 TOP STAT CARDS
            {
                "id": 1,
                "title": "Service Health Status",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
                "targets": [{
                    "datasource": {"type": "prometheus", "uid": DS_UID},
                    "editorMode": "code",
                    "expr": 'up{job="flask_app"}',
                    "range": True,
                    "refId": "A"
                }],
                "fieldConfig": {
                    "defaults": {
                        "mappings": [
                            {"type": "value", "options": {"1": {"color": "green", "text": "HEALTHY (UP)"}}},
                            {"type": "value", "options": {"0": {"color": "red", "text": "DOWN (CRITICAL)"}}}
                        ],
                        "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": 0}, {"color": "green", "value": 1}]},
                        "color": {"mode": "thresholds"}
                    }
                },
                "options": {
                    "reduceOptions": {"calcs": ["lastNotNull"]},
                    "colorMode": "background",
                    "graphMode": "none"
                }
            },
            {
                "id": 2,
                "title": "Host CPU Usage",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 6, "y": 0},
                "targets": [{
                    "datasource": {"type": "prometheus", "uid": DS_UID},
                    "editorMode": "code",
                    "expr": '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)',
                    "range": True,
                    "refId": "A"
                }],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percent",
                        "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": 0}, {"color": "yellow", "value": 70}, {"color": "red", "value": 90}]},
                        "color": {"mode": "thresholds"}
                    }
                },
                "options": {
                    "reduceOptions": {"calcs": ["lastNotNull"]},
                    "colorMode": "value",
                    "graphMode": "area"
                }
            },
            {
                "id": 3,
                "title": "Host Memory Usage",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
                "targets": [{
                    "datasource": {"type": "prometheus", "uid": DS_UID},
                    "editorMode": "code",
                    "expr": '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
                    "range": True,
                    "refId": "A"
                }],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percent",
                        "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": 0}, {"color": "yellow", "value": 75}, {"color": "red", "value": 90}]},
                        "color": {"mode": "thresholds"}
                    }
                },
                "options": {
                    "reduceOptions": {"calcs": ["lastNotNull"]},
                    "colorMode": "value",
                    "graphMode": "area"
                }
            },
            {
                "id": 4,
                "title": "Avg Global API Latency",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 18, "y": 0},
                "targets": [{
                    "datasource": {"type": "prometheus", "uid": DS_UID},
                    "editorMode": "code",
                    "expr": 'sum(rate(http_request_duration_seconds_sum[2m])) / sum(rate(http_request_duration_seconds_count[2m]))',
                    "range": True,
                    "refId": "A"
                }],
                "fieldConfig": {
                    "defaults": {
                        "unit": "s",
                        "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": 0}, {"color": "yellow", "value": 0.3}, {"color": "red", "value": 1.0}]},
                        "color": {"mode": "thresholds"}
                    }
                },
                "options": {
                    "reduceOptions": {"calcs": ["mean"]},
                    "colorMode": "value",
                    "graphMode": "area"
                }
            },
            # ROW 2: LIVE ALERT LIST PANEL (FULL WIDTH OR SIDE-BY-SIDE)
            {
                "id": 10,
                "title": "Active Prometheus & Grafana Alerts (Live Status)",
                "type": "alertlist",
                "gridPos": {"h": 7, "w": 24, "x": 0, "y": 4},
                "options": {
                    "alertInstanceLabelFilter": "",
                    "alertName": "",
                    "dashboardAlerts": False,
                    "groupBy": [],
                    "groupMode": "default",
                    "maxItems": 20,
                    "sortOrder": 3,
                    "stateFilter": {
                        "error": True,
                        "firing": True,
                        "noData": False,
                        "normal": True,
                        "pending": True
                    },
                    "viewMode": "list"
                }
            },
            # ROW 3: HTTP TRAFFIC TIMESERIES (15) + CLEAN DONUT (9)
            {
                "id": 6,
                "title": "HTTP Traffic by Status Code & Name (Requests / sec)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 15, "x": 0, "y": 11},
                "targets": [{
                    "datasource": {"type": "prometheus", "uid": DS_UID},
                    "editorMode": "code",
                    "expr": 'sum(rate(http_requests_total[1m])) by (http_status, http_status_text)',
                    "legendFormat": "HTTP {{http_status}} {{http_status_text}}",
                    "range": True,
                    "refId": "A"
                }],
                "fieldConfig": {
                    "defaults": {
                        "custom": {
                            "drawStyle": "line",
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "fillOpacity": 15,
                            "thresholdsStyle": {"mode": "line"}
                        },
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "red", "value": 0.1}
                            ]
                        },
                        "unit": "reqps"
                    }
                },
                "options": {
                    "legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]}
                }
            },
            {
                "id": 5,
                "title": "Requests by Endpoint (Excl. Root /)",
                "type": "piechart",
                "gridPos": {"h": 8, "w": 9, "x": 15, "y": 11},
                "targets": [{
                    "datasource": {"type": "prometheus", "uid": DS_UID},
                    "editorMode": "code",
                    "expr": 'sum(increase(http_requests_total{endpoint!="/"}[15m])) by (endpoint)',
                    "legendFormat": "{{endpoint}}",
                    "range": True,
                    "refId": "A"
                }],
                "options": {
                    "legend": {"displayMode": "table", "placement": "right", "values": ["value", "percent"]},
                    "pieType": "donut",
                    "reduceOptions": {"calcs": ["lastNotNull"]}
                }
            },
            # ROW 4: LATENCY BREAKDOWN (12) + NETWORK I/O (12)
            {
                "id": 8,
                "title": "Response Latency by Endpoint (p95 / Average)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 19},
                "targets": [
                    {
                        "datasource": {"type": "prometheus", "uid": DS_UID},
                        "editorMode": "code",
                        "expr": 'rate(http_request_duration_seconds_sum{endpoint!="/"}[1m]) / rate(http_request_duration_seconds_count{endpoint!="/"}[1m])',
                        "legendFormat": "{{endpoint}} (avg)",
                        "range": True,
                        "refId": "A"
                    },
                    {
                        "datasource": {"type": "prometheus", "uid": DS_UID},
                        "editorMode": "code",
                        "expr": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{endpoint!="/"}[1m])) by (le, endpoint))',
                        "legendFormat": "{{endpoint}} (p95)",
                        "range": True,
                        "refId": "B"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "s",
                        "custom": {
                            "drawStyle": "line",
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "thresholdsStyle": {"mode": "line"}
                        },
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "red", "value": 0.5}
                            ]
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]}
                }
            },
            {
                "id": 9,
                "title": "Server Network I/O (Throughput)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 19},
                "targets": [
                    {
                        "datasource": {"type": "prometheus", "uid": DS_UID},
                        "editorMode": "code",
                        "expr": 'sum(rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[1m]))',
                        "legendFormat": "Inbound (Receive)",
                        "range": True,
                        "refId": "A"
                    },
                    {
                        "datasource": {"type": "prometheus", "uid": DS_UID},
                        "editorMode": "code",
                        "expr": 'sum(rate(node_network_transmit_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[1m]))',
                        "legendFormat": "Outbound (Transmit)",
                        "range": True,
                        "refId": "B"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "Bps",
                        "custom": {
                            "drawStyle": "line",
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "fillOpacity": 10
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "mean"]}
                }
            }
        ]
    },
    "overwrite": True,
    "folderId": 0
}

req = urllib.request.Request(
    f"{GRAFANA_URL}/api/dashboards/db",
    data=json.dumps(dashboard).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Basic {AUTH}"
    }
)

with urllib.request.urlopen(req) as resp:
    res = resp.read().decode("utf-8")
    print("Dashboard updated successfully:", res)
