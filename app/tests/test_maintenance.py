from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check():
    response = client.get(
        url="/maintenance/health_check",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert 'utc' in payload
