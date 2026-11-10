#!/bin/bash
# =============================================================
# diagnose_dashboard.sh
# Diagnoses why Grafana dashboard panels show no data, then:
#   1. Verifies each PromQL query directly against Prometheus
#   2. Fixes the Grafana datasource if broken
#   3. Imports the dashboard with the correct datasource UID
#   4. Generates traffic so all metrics have live data
# Usage: bash diagnose_dashboard.sh
# =============================================================

BASE="http://localhost:5000"
PROM="http://localhost:9090"
GRAFANA="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASS="admin"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
NC="\033[0m"

ok()   { echo -e "  ${GREEN}✔ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }
fail() { echo -e "  ${RED}✘ $1${NC}"; }
sep()  { echo -e "\n${BLUE}══════════════════════════════════════════${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}══════════════════════════════════════════${NC}"; }

# --------------------------------------------------
# STEP 1: Check all containers are running
# --------------------------------------------------
sep "STEP 1: Container Health"
for NAME in flask-app prometheus grafana; do
  STATUS=$(docker inspect --format '{{.State.Status}}' "$NAME" 2>/dev/null)
  if [ "$STATUS" = "running" ]; then
    ok "$NAME is running"
  else
    fail "$NAME is NOT running (status: ${STATUS:-not found})"
    echo -e "  Fix: ${BLUE}cd /opt/flask-monitoring-cicd && docker compose up -d${NC}"
  fi
done

# --------------------------------------------------
# STEP 2: Check Prometheus scrape targets
# --------------------------------------------------
sep "STEP 2: Prometheus Scrape Targets"
TARGETS=$(curl -s "$PROM/api/v1/targets" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data['data']['activeTargets']:
    print(f\"  job={t['labels'].get('job','?')}  health={t['health']}  lastError='{t.get('lastError','')}'  url={t['scrapeUrl']}\")
" 2>/dev/null)
echo "$TARGETS"
if echo "$TARGETS" | grep -q "flask_app.*up"; then
  ok "flask_app target is UP"
else
  warn "flask_app target may be down or not scraped yet"
fi

# --------------------------------------------------
# STEP 3: Run every dashboard PromQL query against Prometheus
# --------------------------------------------------
sep "STEP 3: PromQL Query Validation"

check_query() {
  local LABEL="$1"
  local QUERY="$2"
  local ENCODED
  ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$QUERY'''))")
  local RESULT
  RESULT=$(curl -s "$PROM/api/v1/query?query=$ENCODED")
  local COUNT
  COUNT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['data']['result']))" 2>/dev/null)
  if [ "$COUNT" -gt 0 ] 2>/dev/null; then
    ok "$LABEL → $COUNT series returned"
  else
    fail "$LABEL → NO DATA (0 series) — panel will be blank"
  fi
}

check_query "Panel 1 - Service Health"     'up{job="flask_app"}'
check_query "Panel 2 - Weather by City"    'sum(increase(weather_api_calls_total[15m])) by (city)'
check_query "Panel 3 - Req by Status"      'sum(rate(http_requests_total[1m])) by (http_status)'
check_query "Panel 4 - Latency by Endpoint" 'rate(http_request_duration_seconds_sum[1m]) / rate(http_request_duration_seconds_count[1m])'

# --------------------------------------------------
# STEP 4: Check and fix Grafana datasource
# --------------------------------------------------
sep "STEP 4: Grafana Datasource Check & Fix"

DS_JSON=$(curl -s -u "$GRAFANA_USER:$GRAFANA_PASS" "$GRAFANA/api/datasources")
DS_UID=$(echo "$DS_JSON" | python3 -c "
import sys, json
sources = json.load(sys.stdin)
for ds in sources:
    if ds.get('type') == 'prometheus' and ds.get('url'):
        print(ds['uid'])
        break
" 2>/dev/null)

DS_NAME=$(echo "$DS_JSON" | python3 -c "
import sys, json
sources = json.load(sys.stdin)
for ds in sources:
    if ds.get('type') == 'prometheus' and ds.get('url'):
        print(ds['name'])
        break
" 2>/dev/null)

if [ -n "$DS_UID" ]; then
  ok "Found working Prometheus datasource: name='$DS_NAME' uid='$DS_UID'"
else
  warn "No working Prometheus datasource found — creating one..."
  CREATE=$(curl -s -X POST -u "$GRAFANA_USER:$GRAFANA_PASS" \
    -H "Content-Type: application/json" \
    "$GRAFANA/api/datasources" \
    -d '{
      "name": "Prometheus",
      "type": "prometheus",
      "url": "http://prometheus:9090",
      "access": "proxy",
      "isDefault": true
    }')
  DS_UID=$(echo "$CREATE" | python3 -c "import sys,json; print(json.load(sys.stdin)['datasource']['uid'])" 2>/dev/null)
  ok "Created datasource with uid='$DS_UID'"
fi

# --------------------------------------------------
# STEP 5: Import dashboard with correct datasource UID
# --------------------------------------------------
sep "STEP 5: Importing Dashboard with Correct Datasource UID"

if [ -z "$DS_UID" ]; then
  fail "Cannot import dashboard — no datasource UID found. Fix datasource first."
  exit 1
fi

echo "  Using datasource UID: $DS_UID"

DASHBOARD_JSON=$(cat << ENDJSON
{
  "dashboard": {
    "title": "Flask Weather & Space Monitoring",
    "uid": "flask-weather-space-v2",
    "timezone": "browser",
    "schemaVersion": 38,
    "refresh": "5s",
    "time": { "from": "now-15m", "to": "now" },
    "panels": [
      {
        "id": 1,
        "title": "Service Health Status",
        "type": "stat",
        "gridPos": { "h": 4, "w": 6, "x": 0, "y": 0 },
        "targets": [{
          "datasource": { "type": "prometheus", "uid": "$DS_UID" },
          "editorMode": "code",
          "expr": "up{job=\\"flask_app\\"}",
          "range": true,
          "refId": "A"
        }],
        "fieldConfig": {
          "defaults": {
            "mappings": [
              { "type": "value", "options": { "1": { "color": "green", "text": "HEALTHY (UP)" } } },
              { "type": "value", "options": { "0": { "color": "red",   "text": "DOWN (CRITICAL)" } } }
            ],
            "thresholds": { "mode": "absolute", "steps": [{"color": "red","value": 0},{"color": "green","value": 1}] },
            "color": { "mode": "thresholds" }
          }
        },
        "options": { "reduceOptions": { "calcs": ["lastNotNull"] }, "orientation": "auto", "colorMode": "background" }
      },
      {
        "id": 2,
        "title": "Weather Lookups by City",
        "type": "barchart",
        "gridPos": { "h": 8, "w": 9, "x": 6, "y": 0 },
        "targets": [{
          "datasource": { "type": "prometheus", "uid": "$DS_UID" },
          "editorMode": "code",
          "expr": "sum(increase(weather_api_calls_total[15m])) by (city)",
          "legendFormat": "{{city}}",
          "range": true,
          "refId": "A"
        }]
      },
      {
        "id": 3,
        "title": "Valid vs Failed Requests (rate/min)",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 9, "x": 15, "y": 0 },
        "targets": [{
          "datasource": { "type": "prometheus", "uid": "$DS_UID" },
          "editorMode": "code",
          "expr": "sum(rate(http_requests_total[1m])) by (http_status)",
          "legendFormat": "HTTP {{http_status}}",
          "range": true,
          "refId": "A"
        }]
      },
      {
        "id": 4,
        "title": "API Response Time by Endpoint (seconds)",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 8 },
        "targets": [{
          "datasource": { "type": "prometheus", "uid": "$DS_UID" },
          "editorMode": "code",
          "expr": "rate(http_request_duration_seconds_sum[1m]) / rate(http_request_duration_seconds_count[1m])",
          "legendFormat": "{{endpoint}}",
          "range": true,
          "refId": "A"
        }]
      },
      {
        "id": 5,
        "title": "Total Requests by Endpoint",
        "type": "stat",
        "gridPos": { "h": 4, "w": 6, "x": 0, "y": 4 },
        "targets": [{
          "datasource": { "type": "prometheus", "uid": "$DS_UID" },
          "editorMode": "code",
          "expr": "sum(http_requests_total) by (endpoint)",
          "legendFormat": "{{endpoint}}",
          "range": true,
          "refId": "A"
        }],
        "options": { "reduceOptions": { "calcs": ["lastNotNull"] }, "colorMode": "background", "orientation": "auto" }
      },
      {
        "id": 6,
        "title": "HTTP 500 Error Rate",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 8 },
        "targets": [{
          "datasource": { "type": "prometheus", "uid": "$DS_UID" },
          "editorMode": "code",
          "expr": "rate(http_requests_total{http_status=\\"500\\"}[1m])",
          "legendFormat": "{{endpoint}} errors/sec",
          "range": true,
          "refId": "A"
        }],
        "fieldConfig": {
          "defaults": {
            "thresholds": { "mode": "absolute", "steps": [{"color":"green","value":0},{"color":"red","value":0.1}] },
            "color": { "mode": "thresholds" }
          }
        }
      }
    ]
  },
  "overwrite": true,
  "folderId": 0
}
ENDJSON
)

IMPORT_RESULT=$(curl -s -X POST \
  -u "$GRAFANA_USER:$GRAFANA_PASS" \
  -H "Content-Type: application/json" \
  "$GRAFANA/api/dashboards/db" \
  -d "$DASHBOARD_JSON")

DASH_URL=$(echo "$IMPORT_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('url',''))" 2>/dev/null)
DASH_STATUS=$(echo "$IMPORT_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null)

if [ "$DASH_STATUS" = "success" ]; then
  ok "Dashboard imported! Open: ${GRAFANA}${DASH_URL}"
else
  fail "Dashboard import failed"
  echo "  Response: $IMPORT_RESULT"
fi

# --------------------------------------------------
# STEP 6: Generate traffic so all panels have live data
# --------------------------------------------------
sep "STEP 6: Generating Live Traffic for All Panels"

echo -e "${YELLOW}Sending traffic to populate all metrics...${NC}"

# /health, /error, / (latency panel)
for i in {1..20}; do
  curl -s "$BASE/"        > /dev/null
  curl -s "$BASE/health"  > /dev/null
  curl -s "$BASE/error"   > /dev/null
  echo -ne "  Basic traffic batch $i/20\r"
  sleep 0.1
done

# /weather valid cities (weather_api_calls_total)
for CITY in delhi mumbai london tokyo delhi delhi mumbai; do
  curl -s "$BASE/weather?city=$CITY" > /dev/null
  echo -e "  Weather: $CITY"
done

# /weather invalid (500s for WeatherAPIFailures alert)
for CITY in paris berlin sydney; do
  curl -s "$BASE/weather?city=$CITY" > /dev/null
  echo -e "  Invalid weather: $CITY → 500"
done

# /space
curl -s "$BASE/space" > /dev/null && echo -e "  Space/ISS: hit"

ok "Traffic complete — all 6 panels should now have data"

# --------------------------------------------------
# STEP 7: Final summary
# --------------------------------------------------
sep "DONE — Summary"
echo -e "  ${GREEN}Dashboard URL : ${GRAFANA}${DASH_URL}${NC}"
echo -e "  ${GREEN}Prometheus    : ${PROM}/alerts${NC}"
echo -e "  ${YELLOW}Tip: Set time range to 'Last 15 minutes' and refresh to '5s' in Grafana${NC}"

