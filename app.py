import time
import requests
from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# Standard HTTP Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP Requests',
    ['method', 'endpoint', 'http_status']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP Request Latency',
    ['endpoint']
)

# Custom Live Weather Metric for Grafana!
CITY_TEMP = Counter(
    'weather_api_calls_total',
    'Total Weather API Lookups by City',
    ['city']
)

CITIES = {
    "delhi": {"lat": 28.61, "lon": 77.23},
    "mumbai": {"lat": 19.07, "lon": 72.87},
    "london": {"lat": 51.50, "lon": -0.12},
    "tokyo": {"lat": 35.67, "lon": 139.65}
}

@app.before_request
def start_timer():
    request.start_time = time.time()

@app.after_request
def record_metrics(response):
    if request.path != '/metrics':
        latency = time.time() - request.start_time
        REQUEST_LATENCY.labels(endpoint=request.path).observe(latency)
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.path,
            http_status=response.status_code
        ).inc()
    return response

@app.route('/health')
def health():
    return jsonify({"status": "UP"}), 200

@app.route('/weather')
def get_weather():
    city = request.args.get('city', 'delhi').lower()
    if city not in CITIES:
        # Passing an invalid city triggers a 500 error for your Prometheus alert!
        return jsonify({"error": f"City '{city}' not supported. Try delhi, mumbai, london, or tokyo."}), 500

    coords = CITIES[city]
    url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&current_weather=true"

    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        weather_data = resp.json().get("current_weather", {})
        CITY_TEMP.labels(city=city).inc()
        return jsonify({
            "city": city.title(),
            "temperature_celsius": weather_data.get("temperature"),
            "windspeed_kmh": weather_data.get("windspeed")
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/space')
def get_iss_location():
    # Live NASA/Open-Notify International Space Station coordinates
    try:
        resp = requests.get("http://api.open-notify.org/iss-now.json", timeout=5)
        resp.raise_for_status()
        return jsonify(resp.json()), 200
    except Exception as e:
        return jsonify({"error": "Upstream NASA/ISS API failed", "details": str(e)}), 500

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
