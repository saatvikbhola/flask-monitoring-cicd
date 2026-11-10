import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(
    page_title="Flask API & Ops Control Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
FLASK_URL = "http://flask-app:5000"
PROM_URL = "http://prometheus:9090"
GRAFANA_URL = "http://localhost:3000"

def get_base_url():
    try:
        requests.get("http://flask-app:5000/health", timeout=1)
        return "http://flask-app:5000"
    except Exception:
        return "http://localhost:5000"

def get_prom_url():
    try:
        requests.get("http://prometheus:9090/-/healthy", timeout=1)
        return "http://prometheus:9090"
    except Exception:
        return "http://localhost:9090"

BASE_URL = get_base_url()
PROMETHEUS_URL = get_prom_url()

st.title("⚡ Flask API & Server Operations Dashboard")
st.markdown("Interactive UI to test global weather lookups, simulate traffic bursts, and inspect real-time Prometheus metrics.")

# Sidebar Quick Links
with st.sidebar:
    st.header("🔗 Quick Links")
    st.markdown(f"- [Open Grafana Dashboard]({GRAFANA_URL}/d/flask-weather-space-v2/production-server-and-api-monitoring)")
    st.markdown(f"- [Prometheus Alerts View]({PROMETHEUS_URL}/alerts)")
    st.markdown(f"- [Prometheus Targets]({PROMETHEUS_URL}/targets)")
    st.markdown("---")
    st.subheader("System Status")
    st.write(f"**Flask Target**: `{BASE_URL}`")
    st.write(f"**Prometheus Target**: `{PROMETHEUS_URL}`")
    st.write(f"**Grafana**: `{GRAFANA_URL}`")

tab1, tab2, tab3, tab4 = st.tabs(["🌤️ Global Weather Search", "🔥 Traffic & Alert Simulator", "📊 Live Metrics Snapshot", "🚨 Active Alerts"])

# ── TAB 1: WEATHER SEARCH ──
with tab1:
    st.subheader("Global Live Weather Query")
    st.markdown("Search any real city or town in the world via the Open-Meteo Geocoding + Weather API.")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        city_input = st.text_input("Enter city name:", value="Tokyo")
        if st.button("Query Weather", type="primary"):
            with st.spinner(f"Querying weather for {city_input}..."):
                try:
                    res = requests.get(f"{BASE_URL}/weather", params={"city": city_input}, timeout=6)
                    data = res.json()
                    status_code = res.status_code
                    status_text = data.get("http_status_text", "Unknown")
                    
                    if status_code == 200:
                        st.success(f"HTTP {status_code} {status_text}")
                        col_m1, col_m2 = st.columns(2)
                        with col_m1:
                            st.metric("Temperature", f"{data.get('temperature_celsius')} °C")
                        with col_m2:
                            st.metric("Wind Speed", f"{data.get('windspeed_kmh')} km/h")
                        st.write(f"**City Name:** {data.get('city')}")
                        st.write(f"**Country:** {data.get('country')}")
                        st.write(f"**Coordinates:** Lat `{data.get('latitude')}`, Lon `{data.get('longitude')}`")
                    elif status_code == 404:
                        st.error(f"HTTP {status_code} {status_text}: {data.get('error')}")
                        st.info(data.get('hint', ''))
                    else:
                        st.warning(f"HTTP {status_code} {status_text}: {data.get('error')}")
                except Exception as e:
                    st.error(f"Request failed: {e}")

    with col2:
        st.info("💡 **Tips**:\n- Real cities (e.g., Delhi, Berlin, Kathmandu, Ushuaia) return `200 OK`.\n- Fake or misspelled names return `404 Not Found`.\n- Every query automatically feeds the Grafana graphs!")

# ── TAB 2: TRAFFIC & ALERT TRIGGER ──
with tab2:
    st.subheader("Simulate Traffic & Trigger Alerts")
    st.markdown("Easily fire requests to test your Prometheus alert rules and observe Grafana graphs.")
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        st.markdown("#### 1. Trigger HTTP 500 (Internal Server Error)")
        count_500 = st.slider("Number of 500 requests", 5, 50, 15)
        if st.button("Trigger 500 Errors"):
            with st.spinner("Sending 500 errors..."):
                for _ in range(count_500):
                    requests.get(f"{BASE_URL}/error")
                    time.sleep(0.04)
            st.success(f"Sent {count_500} requests to `/error`! Observe `HighErrorRate` in Grafana.")

    with col_b:
        st.markdown("#### 2. Trigger HTTP 404 (Invalid Cities)")
        count_404 = st.slider("Number of 404 requests", 5, 50, 15)
        if st.button("Trigger 404 Bad City Lookups"):
            with st.spinner("Sending invalid city lookups..."):
                for i in range(count_404):
                    requests.get(f"{BASE_URL}/weather", params={"city": f"notacity_{i}_abc"})
                    time.sleep(0.04)
            st.success(f"Sent {count_404} invalid lookups! Observe `HighNotFoundRate`.")

    with col_c:
        st.markdown("#### 3. High Request Burst (Load Test)")
        count_burst = st.slider("Burst request count", 20, 100, 30)
        if st.button("Send Request Burst"):
            with st.spinner("Sending load burst..."):
                for _ in range(count_burst):
                    requests.get(f"{BASE_URL}/health")
                    time.sleep(0.02)
            st.success(f"Sent burst traffic! Check `HighRequestRate` in Grafana.")

# ── TAB 3: LIVE METRICS SNAPSHOT ──
with tab3:
    st.subheader("Prometheus Live Request Metrics")
    if st.button("🔄 Refresh Metrics"):
        st.rerun()

    try:
        res = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": "http_requests_total"}, timeout=4)
        records = []
        if res.status_code == 200:
            results = res.json().get("data", {}).get("result", [])
            for item in results:
                metric = item.get("metric", {})
                records.append({
                    "Method": metric.get("method"),
                    "Endpoint": metric.get("endpoint"),
                    "HTTP Status": f"{metric.get('http_status')} {metric.get('http_status_text', '')}",
                    "Total Count": float(item.get("value", [0, 0])[1])
                })
        
        if records:
            df = pd.DataFrame(records)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No request metrics recorded yet. Generate traffic in Tab 2!")
    except Exception as e:
        st.error(f"Failed to query Prometheus: {e}")

# ── TAB 4: ACTIVE ALERTS ──
with tab4:
    st.subheader("Prometheus Alerting Status")
    try:
        res = requests.get(f"{PROMETHEUS_URL}/api/v1/alerts", timeout=4)
        if res.status_code == 200:
            alerts = res.json().get("data", {}).get("alerts", [])
            if alerts:
                for a in alerts:
                    state = a.get("state")
                    name = a.get("labels", {}).get("alertname")
                    severity = a.get("labels", {}).get("severity", "unknown")
                    desc = a.get("annotations", {}).get("summary", "")
                    
                    if state == "firing":
                        st.error(f"🔥 **{name}** [{severity.upper()}] - {desc}")
                    elif state == "pending":
                        st.warning(f"⏳ **{name}** [{severity.upper()}] - {desc} (Pending trigger threshold)")
                    else:
                        st.info(f"ℹ️ **{name}** - State: {state}")
            else:
                st.success("🎉 All systems green! No alerts firing or pending.")
    except Exception as e:
        st.error(f"Could not load alerts from Prometheus: {e}")
