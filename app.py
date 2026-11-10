import time
import requests
from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# ── HTTP Status Code name map ───────────────────────────────
HTTP_STATUS_NAMES = {
    200: "OK",
    201: "Created",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    408: "Request Timeout",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}

# ── Prometheus Metrics ──────────────────────────────────────
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP Requests',
    ['method', 'endpoint', 'http_status', 'http_status_text']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP Request Latency',
    ['endpoint']
)
WEATHER_ERRORS = Counter(
    'weather_api_errors_total',
    'Total Weather API Failures by reason',
    ['reason']
)

# ── Request Hooks ───────────────────────────────────────────
@app.before_request
def start_timer():
    request.start_time = time.time()

@app.after_request
def record_metrics(response):
    if request.path != '/metrics':
        latency = time.time() - request.start_time
        REQUEST_LATENCY.labels(endpoint=request.path).observe(latency)
        status_code = response.status_code
        status_text = HTTP_STATUS_NAMES.get(status_code, "Unknown")
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.path,
            http_status=str(status_code),
            http_status_text=status_text
        ).inc()
    return response

# ── Routes ──────────────────────────────────────────────────
@app.route('/health')
def health():
    return jsonify({
        "status": "UP",
        "http_status": 200,
        "http_status_text": HTTP_STATUS_NAMES[200]
    }), 200

@app.route('/error')
def trigger_error():
    return jsonify({
        "error": "Internal Server Error",
        "http_status": 500,
        "http_status_text": HTTP_STATUS_NAMES[500]
    }), 500

@app.route('/weather')
def get_weather():
    city = request.args.get('city', '').strip()
    if not city:
        return jsonify({
            "error": "Missing 'city' parameter",
            "http_status": 400,
            "http_status_text": HTTP_STATUS_NAMES[400],
            "hint": "Try /weather?city=<any_city_name_in_the_world>"
        }), 400

    # 1. Geocoding Search: Look up ANY city in the world dynamically via Open-Meteo Geocoding API
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
    try:
        geo_resp = requests.get(geo_url, timeout=5)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
    except requests.Timeout:
        WEATHER_ERRORS.labels(reason="upstream_timeout").inc()
        return jsonify({
            "error": "Geocoding API timed out",
            "http_status": 504,
            "http_status_text": HTTP_STATUS_NAMES[504]
        }), 504
    except Exception as e:
        WEATHER_ERRORS.labels(reason="upstream_error").inc()
        return jsonify({
            "error": "Upstream geocoding API lookup failed",
            "details": str(e),
            "http_status": 502,
            "http_status_text": HTTP_STATUS_NAMES[502]
        }), 502

    results = geo_data.get("results")
    if not results or len(results) == 0:
        WEATHER_ERRORS.labels(reason="invalid_city").inc()
        return jsonify({
            "error": f"City '{city}' was not found anywhere in the global geocoding database.",
            "http_status": 404,
            "http_status_text": HTTP_STATUS_NAMES[404],
            "hint": "Please verify the spelling of the city."
        }), 404

    city_info = results[0]
    city_name = city_info.get("name", city.title())
    country = city_info.get("country", "Unknown")
    lat = city_info.get("latitude")
    lon = city_info.get("longitude")

    # 2. Fetch Live Weather for resolved coordinates
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current_weather=true"
    )
    try:
        resp = requests.get(weather_url, timeout=5)
        resp.raise_for_status()
        weather_data = resp.json().get("current_weather", {})
        return jsonify({
            "city": city_name,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "temperature_celsius": weather_data.get("temperature"),
            "windspeed_kmh": weather_data.get("windspeed"),
            "http_status": 200,
            "http_status_text": HTTP_STATUS_NAMES[200]
        }), 200
    except requests.Timeout:
        WEATHER_ERRORS.labels(reason="upstream_timeout").inc()
        return jsonify({
            "error": "Weather forecast API timed out",
            "http_status": 504,
            "http_status_text": HTTP_STATUS_NAMES[504]
        }), 504
    except Exception as e:
        WEATHER_ERRORS.labels(reason="upstream_error").inc()
        return jsonify({
            "error": "Upstream weather forecast API failed",
            "details": str(e),
            "http_status": 502,
            "http_status_text": HTTP_STATUS_NAMES[502]
        }), 502

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
