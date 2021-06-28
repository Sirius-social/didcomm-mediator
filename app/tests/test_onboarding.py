import json

from fastapi.testclient import TestClient
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol.messages import Invitation, ConnRequest, ConnResponse
from sirius_sdk.encryption import P2PConnection
from sirius_sdk.agent.aries_rfc.feature_0048_trust_ping.messages import Ping

from app.main import app
from app.settings import RELAY_KEYPAIR


def test_establish_connection(random_me: (str, str, str)):
    client = TestClient(app)
    did, verkey, secret = random_me
    with client.websocket_connect("/") as websocket:
        invitation = Invitation(label='Agent', recipient_keys=[verkey])
        websocket.send_bytes(json.dumps(invitation).encode())
        print('#')


def test_trust_ping(random_me: (str, str, str)):
    client = TestClient(app)
    did, verkey, secret = random_me
    p2p = P2PConnection(my_keys=(verkey, secret), their_verkey=RELAY_KEYPAIR[0])
    with client.websocket_connect("/") as websocket:
        ping = Ping(response_requested=True)
        packed = p2p.pack(ping)
        websocket.send_bytes(packed)
        packed = websocket.receive_bytes()
        msg = p2p.unpack(enc_message=packed)
        assert 'ping_response' in msg['@type']
        assert msg['~thread']['thid'] == ping.id
