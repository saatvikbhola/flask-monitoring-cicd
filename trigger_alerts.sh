#!/bin/bash
# =============================================================
# trigger_alerts.sh — Production Alert Rule Trigger Suite
# Usage:
#   bash trigger_alerts.sh error      # Triggers HighServerErrorRate (5xx ratio > 5%)
#   bash trigger_alerts.sh latency    # Triggers DegradedApiLatency (p95 > 1.0s)
#   bash trigger_alerts.sh down       # Triggers ServiceDown (stops container)
#   bash trigger_alerts.sh gateway    # Triggers UpstreamGatewayOutage (502/504)
#   bash trigger_alerts.sh cpu        # Triggers HostCpuSaturation (> 85% CPU load)
#   bash trigger_alerts.sh status     # Check Prometheus & Grafana alert states
# =============================================================

BASE="http://localhost:5000"
PROM="http://localhost:9090"
GRAFANA="http://localhost:3000"

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
NC="\033[0m"

sep() {
  echo -e "\n${BLUE}══════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}  $1${NC}"
  echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
}

# -------------------------------------------------------------
# 1. Trigger HighServerErrorRate
# Sends continuous 500 errors to drive 5xx error percentage > 5%
# -------------------------------------------------------------
trigger_5xx() {
  sep "Triggering: HighServerErrorRate (5xx > 5% of traffic)"
  echo -e "${YELLOW}Sending sustained HTTP 500 errors to /error...${NC}"
  echo "Target rule: 5xx ratio > 5% for 2 minutes."
  echo "Sending batch for 45 seconds (press Ctrl+C to abort early)..."
  
  END=$((SECONDS + 45))
  COUNT=0
  while [ $SECONDS -lt $END ]; do
    curl -s "$BASE/error" > /dev/null &
    curl -s "$BASE/health" > /dev/null &
    COUNT=$((COUNT + 2))
    echo -ne "  Requests sent: $COUNT\r"
    sleep 0.1
  done
  wait
  echo -e "\n${GREEN}✔ Traffic sent. The alert will transition from PENDING -> FIRING in Prometheus / Grafana.${NC}"
  echo -e "Check live: ${BLUE}$PROM/alerts${NC} or ${BLUE}$GRAFANA/d/flask-weather-space-v2/production-server-and-api-monitoring${NC}"
}

# -------------------------------------------------------------
# 2. Trigger DegradedApiLatency
# Simulates slow requests to drive p95 latency > 1.0s
# -------------------------------------------------------------
trigger_latency() {
  sep "Triggering: DegradedApiLatency (p95 > 1.0s)"
  echo -e "${YELLOW}Flooding slow endpoint to push p95 latency above 1 second...${NC}"
  
  for i in {1..60}; do
    curl -s "$BASE/weather?city=Tokyo" > /dev/null &
    curl -s "$BASE/weather?city=London" > /dev/null &
    echo -ne "  Batch $i/60\r"
    sleep 0.15
  done
  wait
  echo -e "\n${GREEN}✔ Slow request batch sent. Observe Latency tile on Grafana.${NC}"
}

# -------------------------------------------------------------
# 3. Trigger ServiceDown
# Stops the container to trigger the P0 ServiceDown alert
# -------------------------------------------------------------
trigger_down() {
  sep "Triggering: ServiceDown (Flask app down for > 1m)"
  echo -e "${RED}Stopping container 'flask-app'...${NC}"
  docker stop flask-app
  echo -e "${YELLOW}Container stopped. ServiceDown will show pending, then FIRING in ~1 minute.${NC}"
  echo "Prometheus status: $PROM/alerts"
  echo ""
  read -p "Press [ENTER] to restart flask-app and resolve the alert: "
  docker start flask-app
  echo -e "${GREEN}✔ Container restarted. Alert will resolve automatically.${NC}"
}

# -------------------------------------------------------------
# 4. Trigger UpstreamGatewayOutage
# Simulates upstream 502/504 errors
# -------------------------------------------------------------
trigger_gateway() {
  sep "Triggering: UpstreamGatewayOutage (502 / 504 Gateway errors)"
  echo -e "${YELLOW}Sending invalid upstream triggers...${NC}"
  for i in {1..30}; do
    curl -s "$BASE/weather?city=invalidcity_timeout_test" > /dev/null
    sleep 0.1
  done
  echo -e "${GREEN}✔ Upstream error simulation finished.${NC}"
}

# -------------------------------------------------------------
# 5. Trigger HostCpuSaturation
# Spawns brief CPU stress load to drive CPU > 85%
# -------------------------------------------------------------
trigger_cpu() {
  sep "Triggering: HostCpuSaturation (Host CPU > 85%)"
  echo -e "${YELLOW}Spawning 4 worker processes for 30 seconds...${NC}"
  python3 -c "
import time, multiprocessing
def f():
    t = time.time() + 30
    while time.time() < t:
        _ = 2147483647 * 2147483647
procs = [multiprocessing.Process(target=f) for _ in range(multiprocessing.cpu_count())]
for p in procs: p.start()
for p in procs: p.join()
" &
  echo -e "${GREEN}✔ CPU stress running in background for 30s. Watch 'Host CPU Usage' spike on Grafana.${NC}"
}

# -------------------------------------------------------------
# Check Alert Status
# -------------------------------------------------------------
check_status() {
  sep "Active Prometheus Alerts Snapshot"
  curl -s "$PROM/api/v1/alerts" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('data', {}).get('alerts', [])
if not data:
    print('  No alerts active. All systems normal.')
for a in data:
    print(f\"  [{a.get('state').upper()}] {a['labels'].get('alertname')} ({a['labels'].get('severity')}) - {a['annotations'].get('summary')}\")
"
}

case "${1:-menu}" in
  error)    trigger_5xx ;;
  latency)  trigger_latency ;;
  down)     trigger_down ;;
  gateway)  trigger_gateway ;;
  cpu)      trigger_cpu ;;
  status)   check_status ;;
  *)
    echo "======================================================"
    echo "  PRODUCTION ALERT TRIGGER SUITE"
    echo "======================================================"
    echo "Usage: bash trigger_alerts.sh <command>"
    echo ""
    echo "Commands:"
    echo "  bash trigger_alerts.sh error    -> Fire HighServerErrorRate (5xx > 5%)"
    echo "  bash trigger_alerts.sh down     -> Fire ServiceDown (stop container)"
    echo "  bash trigger_alerts.sh latency  -> Fire DegradedApiLatency (p95 > 1s)"
    echo "  bash trigger_alerts.sh cpu      -> Fire HostCpuSaturation (CPU > 85%)"
    echo "  bash trigger_alerts.sh gateway  -> Fire UpstreamGatewayOutage (502/504)"
    echo "  bash trigger_alerts.sh status   -> Inspect active Prometheus alerts"
    echo "======================================================"
    ;;
esac
