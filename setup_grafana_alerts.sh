#!/bin/bash
# =============================================================
# setup_grafana_alerts.sh
# Creates Grafana alert rules (via Grafana API) that mirror
# the Prometheus alert_rules.yml — with named HTTP status codes.
# Usage: bash setup_grafana_alerts.sh
# =============================================================

GRAFANA="http://localhost:3000"
PROM="http://localhost:9090"
USER="admin"
PASS="admin"
GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; BLUE="\033[0;34m"; NC="\033[0m"

ok()   { echo -e "  ${GREEN}✔ $1${NC}"; }
fail() { echo -e "  ${RED}✘ $1${NC}"; }
sep()  { echo -e "\n${BLUE}══════════════════════════════════════════${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}══════════════════════════════════════════${NC}"; }

# ── Get Prometheus datasource UID ───────────────────────────
sep "Getting Prometheus Datasource UID"
DS_UID=$(curl -s -u "$USER:$PASS" "$GRAFANA/api/datasources" | python3 -c "
import sys, json
for ds in json.load(sys.stdin):
    if ds.get('type') == 'prometheus' and ds.get('url'):
        print(ds['uid']); break
" 2>/dev/null)

if [ -z "$DS_UID" ]; then
  fail "No Prometheus datasource found. Run diagnose_dashboard.sh first."
  exit 1
fi
ok "Datasource UID: $DS_UID"

# ── Create alert rule folder ─────────────────────────────────
sep "Creating Grafana Alert Folder"
FOLDER=$(curl -s -X POST -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  "$GRAFANA/api/folders" \
  -d '{"title":"Flask Monitoring Alerts","uid":"flask-alerts-folder"}')
FOLDER_UID=$(echo "$FOLDER" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('uid','flask-alerts-folder'))" 2>/dev/null)
ok "Folder UID: $FOLDER_UID"

# ── Helper: create one alert rule ───────────────────────────
create_alert() {
  local TITLE="$1"
  local EXPR="$2"
  local SUMMARY="$3"
  local FOR_SEC="$4"
  local SEVERITY="$5"

  local PAYLOAD
  PAYLOAD=$(python3 -c "
import json, sys
rule = {
  'title': '$TITLE',
  'condition': 'C',
  'data': [
    {
      'refId': 'A',
      'datasourceUid': '$DS_UID',
      'queryType': '',
      'relativeTimeRange': {'from': 300, 'to': 0},
      'model': {
        'editorMode': 'code',
        'expr': '''$EXPR''',
        'intervalMs': 1000,
        'maxDataPoints': 43200,
        'refId': 'A',
        'instant': False,
        'range': True
      }
    },
    {
      'refId': 'B',
      'datasourceUid': '-100',
      'queryType': '',
      'relativeTimeRange': {'from': 300, 'to': 0},
      'model': {
        'conditions': [{
          'evaluator': {'params': [0], 'type': 'gt'},
          'operator': {'type': 'and'},
          'query': {'params': ['A']},
          'reducer': {'params': [], 'type': 'last'},
          'type': 'query'
        }],
        'datasource': {'type': '__expr__', 'uid': '-100'},
        'hide': False,
        'intervalMs': 1000,
        'maxDataPoints': 43200,
        'refId': 'B',
        'type': 'classic_conditions'
      }
    },
    {
      'refId': 'C',
      'datasourceUid': '-100',
      'queryType': '',
      'relativeTimeRange': {'from': 300, 'to': 0},
      'model': {
        'conditions': [{
          'evaluator': {'params': [0], 'type': 'gt'},
          'operator': {'type': 'and'},
          'query': {'params': ['B']},
          'reducer': {'params': [], 'type': 'last'},
          'type': 'query'
        }],
        'datasource': {'type': '__expr__', 'uid': '-100'},
        'hide': False,
        'intervalMs': 1000,
        'maxDataPoints': 43200,
        'refId': 'C',
        'type': 'classic_conditions'
      }
    }
  ],
  'folderUID': '$FOLDER_UID',
  'ruleGroup': 'flask-alert-group',
  'for': '${FOR_SEC}s',
  'labels': {'severity': '$SEVERITY'},
  'annotations': {'summary': '$SUMMARY'},
  'noDataState': 'NoData',
  'execErrState': 'Error',
  'isPaused': False
}
print(json.dumps(rule))
")

  local RESULT
  RESULT=$(curl -s -X POST -u "$USER:$PASS" \
    -H "Content-Type: application/json" \
    "$GRAFANA/api/v1/provisioning/alert-rules" \
    -d "$PAYLOAD")

  local ID
  ID=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
  if [ -n "$ID" ] && [ "$ID" != "None" ]; then
    ok "$TITLE (id=$ID)"
  else
    local ERR
    ERR=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message', d))" 2>/dev/null)
    fail "$TITLE → $ERR"
  fi
}

# ── Create all alert rules ───────────────────────────────────
sep "Creating Grafana Alert Rules"

create_alert \
  "ApplicationDown" \
  'up{job="flask_app"} == 0' \
  "Flask API is DOWN — container may have crashed" \
  "10" "critical"

create_alert \
  "HighErrorRate — HTTP 500 Internal Server Error" \
  'rate(http_requests_total{http_status="500",http_status_text="Internal Server Error"}[1m]) > 0.1' \
  "HTTP 500 rate > 0.1/sec for 15s" \
  "15" "critical"

create_alert \
  "HighNotFoundRate — HTTP 404 Not Found" \
  'rate(http_requests_total{http_status="404",http_status_text="Not Found"}[1m]) > 0.2' \
  "Many 404s on /weather — invalid city names being queried" \
  "20" "warning"

create_alert \
  "HighLatency — p95 above 500ms" \
  'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[2m])) > 0.5' \
  "API p95 latency above 500ms for 30s" \
  "30" "warning"

create_alert \
  "HighRequestRate — Traffic Spike" \
  'rate(http_requests_total[1m]) > 10' \
  "More than 10 requests/sec — possible flood or loop" \
  "20" "warning"

create_alert \
  "WeatherInvalidCityErrors" \
  'rate(weather_api_errors_total{reason="invalid_city"}[2m]) > 0.05' \
  "Clients sending unsupported city names to /weather" \
  "20" "warning"

create_alert \
  "WeatherUpstreamTimeout — 504 Gateway Timeout" \
  'rate(weather_api_errors_total{reason="upstream_timeout"}[2m]) > 0.02' \
  "Open-Meteo weather API timing out" \
  "20" "warning"

create_alert \
  "SpaceAPIFailures — 502/504" \
  'rate(http_requests_total{endpoint="/space",http_status=~"502|504"}[2m]) > 0.05' \
  "ISS API returning 502 Bad Gateway or 504 Gateway Timeout" \
  "20" "warning"

create_alert \
  "NoIncomingTraffic" \
  'rate(http_requests_total[5m]) == 0' \
  "Flask app receiving zero requests for 5+ minutes" \
  "60" "info"

create_alert \
  "HighBadRequestRate — HTTP 400 Bad Request" \
  'rate(http_requests_total{http_status="400",http_status_text="Bad Request"}[1m]) > 0.1' \
  "Many /weather calls missing the city parameter" \
  "20" "info"

# ── Reload Prometheus to pick up alert_rules.yml changes ─────
sep "Reloading Prometheus Alert Rules"
docker restart prometheus > /dev/null 2>&1 && ok "Prometheus restarted with new alert_rules.yml" || fail "Prometheus restart failed"

# ── Rebuild Flask container with new app.py ──────────────────
sep "Rebuilding Flask Container"
cd /opt/flask-monitoring-cicd
docker compose up -d --build flask-app 2>&1 | tail -4
sleep 4

# ── Quick smoke test ─────────────────────────────────────────
sep "Smoke Test — New Endpoints"
echo -e "${YELLOW}GET /cities${NC}"
curl -s http://localhost:5000/cities | python3 -m json.tool | grep -E '"total"|"India"|"UK"' | head -5

echo -e "\n${YELLOW}GET /weather?city=paris${NC}"
curl -s "http://localhost:5000/weather?city=paris"

echo -e "\n${YELLOW}GET /weather?city=xyz (fake city)${NC}"
curl -s "http://localhost:5000/weather?city=xyz"

echo -e "\n${YELLOW}GET /weather (no param → 400 Bad Request)${NC}"
curl -s "http://localhost:5000/weather"

echo -e "\n${YELLOW}GET /weather?city=tokyo${NC}"
curl -s "http://localhost:5000/weather?city=tokyo"

sep "DONE"
echo -e "  ${GREEN}Grafana Alerts : $GRAFANA/alerting/list${NC}"
echo -e "  ${GREEN}Prometheus     : $PROM/alerts${NC}"
echo -e "  ${GREEN}City list      : http://localhost:5000/cities${NC}"

