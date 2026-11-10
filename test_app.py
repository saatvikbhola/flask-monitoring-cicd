from unittest.mock import patch, MagicMock
import requests
from app import app

# ── 1. Basic Endpoints ──────────────────────────────────────────

def test_health_endpoint():
    client = app.test_client()
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {"status": "UP", "http_status": 200, "http_status_text": "OK"}
    print(f"\n   [PASS] Health check verified: {response.json}")

def test_metrics_endpoint():
    client = app.test_client()
    response = client.get('/metrics')
    assert response.status_code == 200
    assert b'http_requests_total' in response.data
    print(f"\n   [PASS] Prometheus metrics scraped successfully ({len(response.data)} bytes)")

def test_error_endpoint():
    client = app.test_client()
    response = client.get('/error')
    assert response.status_code == 500
    assert response.json["http_status"] == 500
    assert response.json["http_status_text"] == "Internal Server Error"
    print("\n   [PASS] /error correctly triggered HTTP 500 Internal Server Error")

# ── 2. Weather Endpoint: Client Errors (400, 404) ───────────────

def test_weather_missing_param():
    client = app.test_client()
    response = client.get('/weather')
    assert response.status_code == 400
    assert response.json["http_status_text"] == "Bad Request"
    print("\n   [PASS] Missing ?city= correctly handled with HTTP 400 Bad Request")

def test_weather_empty_param():
    client = app.test_client()
    response = client.get('/weather?city=   ')
    assert response.status_code == 400
    assert response.json["http_status_text"] == "Bad Request"
    print("\n   [PASS] Empty whitespace ?city= correctly handled with HTTP 400 Bad Request")

@patch('requests.get')
def test_weather_invalid_city(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": []}
    mock_get.return_value = mock_resp

    client = app.test_client()
    response = client.get('/weather?city=notarealcity_xyz123')
    assert response.status_code == 404
    assert response.json["http_status"] == 404
    assert response.json["http_status_text"] == "Not Found"
    print("\n   [PASS] Fake city lookup returned HTTP 404 Not Found")

# ── 3. Weather Endpoint: Success (200 OK) ───────────────────────

@patch('requests.get')
def test_weather_valid_city(mock_get):
    mock_geo_resp = MagicMock()
    mock_geo_resp.status_code = 200
    mock_geo_resp.json.return_value = {
        "results": [{
            "name": "Tokyo",
            "country": "Japan",
            "latitude": 35.68,
            "longitude": 139.69
        }]
    }

    mock_weather_resp = MagicMock()
    mock_weather_resp.status_code = 200
    mock_weather_resp.json.return_value = {
        "current_weather": {
            "temperature": 15.2,
            "windspeed": 8.5
        }
    }

    mock_get.side_effect = [mock_geo_resp, mock_weather_resp]

    client = app.test_client()
    response = client.get('/weather?city=Tokyo')
    assert response.status_code == 200
    data = response.json
    assert data["city"] == "Tokyo"
    assert data["country"] == "Japan"
    assert data["temperature_celsius"] == 15.2
    assert data["windspeed_kmh"] == 8.5
    assert data["http_status"] == 200
    assert data["http_status_text"] == "OK"
    print(f"\n   [PASS] Weather lookup for {data['city']}, {data['country']} returned 200 OK ({data['temperature_celsius']}°C)")

# ── 4. Weather Endpoint: Upstream Errors (502, 504) ────────────

@patch('requests.get')
def test_weather_geocoding_timeout_504(mock_get):
    mock_get.side_effect = requests.Timeout("Geocoding connection timed out")

    client = app.test_client()
    response = client.get('/weather?city=Tokyo')
    assert response.status_code == 504
    assert response.json["http_status"] == 504
    assert response.json["http_status_text"] == "Gateway Timeout"
    print("\n   [PASS] Upstream Geocoding timeout properly returned HTTP 504 Gateway Timeout")

@patch('requests.get')
def test_weather_geocoding_upstream_failure_502(mock_get):
    mock_get.side_effect = requests.RequestException("Geocoding upstream failed")

    client = app.test_client()
    response = client.get('/weather?city=Tokyo')
    assert response.status_code == 502
    assert response.json["http_status"] == 502
    assert response.json["http_status_text"] == "Bad Gateway"
    print("\n   [PASS] Upstream Geocoding error properly returned HTTP 502 Bad Gateway")

@patch('requests.get')
def test_weather_forecast_timeout_504(mock_get):
    mock_geo_resp = MagicMock()
    mock_geo_resp.status_code = 200
    mock_geo_resp.json.return_value = {
        "results": [{"name": "Tokyo", "country": "Japan", "latitude": 35.68, "longitude": 139.69}]
    }

    mock_get.side_effect = [mock_geo_resp, requests.Timeout("Forecast API timed out")]

    client = app.test_client()
    response = client.get('/weather?city=Tokyo')
    assert response.status_code == 504
    assert response.json["http_status"] == 504
    assert response.json["http_status_text"] == "Gateway Timeout"
    print("\n   [PASS] Upstream Forecast timeout properly returned HTTP 504 Gateway Timeout")

@patch('requests.get')
def test_weather_forecast_upstream_failure_502(mock_get):
    mock_geo_resp = MagicMock()
    mock_geo_resp.status_code = 200
    mock_geo_resp.json.return_value = {
        "results": [{"name": "Tokyo", "country": "Japan", "latitude": 35.68, "longitude": 139.69}]
    }

    mock_get.side_effect = [mock_geo_resp, requests.RequestException("Forecast API failed")]

    client = app.test_client()
    response = client.get('/weather?city=Tokyo')
    assert response.status_code == 502
    assert response.json["http_status"] == 502
    assert response.json["http_status_text"] == "Bad Gateway"
    print("\n   [PASS] Upstream Forecast error properly returned HTTP 502 Bad Gateway")
