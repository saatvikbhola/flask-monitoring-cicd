from app import app

def test_health_endpoint():
    client = app.test_client()
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {"status": "UP"}

def test_metrics_endpoint():
    client = app.test_client()
    response = client.get('/metrics')
    assert response.status_code == 200
    assert b'http_requests_total' in response.data
