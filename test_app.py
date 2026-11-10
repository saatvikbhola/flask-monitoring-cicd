from app import app

def test_health_endpoint():
    client = app.test_client()
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {"status": "UP", "http_status": 200, "http_status_text": "OK"}

def test_metrics_endpoint():
    client = app.test_client()
    response = client.get('/metrics')
    assert response.status_code == 200
    assert b'http_requests_total' in response.data

def test_weather_valid_city():
    client = app.test_client()
    response = client.get('/weather?city=Tokyo')
    assert response.status_code == 200
    data = response.json
    assert data["city"] == "Tokyo"
    assert "temperature_celsius" in data
    assert "windspeed_kmh" in data
    assert data["http_status_text"] == "OK"

def test_weather_invalid_city():
    client = app.test_client()
    response = client.get('/weather?city=notarealcity_xyz123')
    assert response.status_code == 404
    data = response.json
    assert data["http_status"] == 404
    assert data["http_status_text"] == "Not Found"

def test_weather_missing_param():
    client = app.test_client()
    response = client.get('/weather')
    assert response.status_code == 400
    data = response.json
    assert data["http_status"] == 400
    assert data["http_status_text"] == "Bad Request"

def test_error_endpoint():
    client = app.test_client()
    response = client.get('/error')
    assert response.status_code == 500
    data = response.json
    assert data["http_status"] == 500
    assert data["http_status_text"] == "Internal Server Error"
