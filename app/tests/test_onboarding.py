from fastapi.testclient import TestClient

from app.main import app


def test_websocket(random_keypair: (str, str)):
    client = TestClient(app)
    with client.websocket_connect("/") as websocket:
        data = websocket.receive_json()
        print('qq')
