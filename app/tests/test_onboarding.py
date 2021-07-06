import json
import asyncio
import hashlib
from time import sleep

import sirius_sdk
from databases import Database
from fastapi.testclient import TestClient
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol.messages import Invitation, \
    ConnResponse, ConnProtocolMessage
from sirius_sdk.encryption import P2PConnection, unpack_message, pack_message
from sirius_sdk.agent.aries_rfc.feature_0048_trust_ping.messages import Ping
from sirius_sdk.messaging import restore_message_instance

from app.main import app
from app.dependencies import get_db
from app.settings import KEYPAIR, FCM_SERVICE_TYPE, MEDIATOR_SERVICE_TYPE
from app.core.crypto import MediatorCrypto
from app.db.crud import load_agent, load_endpoint

from .helpers import override_sirius_sdk, override_get_db


WS_ENDPOINT = 'ws://'


def test_establish_connection(test_database: Database, random_me: (str, str, str), random_fcm_device_id: str):
    """Check step-by step AriesRFC 0160 while agent establish P2P with Mediator
    """
    # Override original database with test one
    app.dependency_overrides[get_db] = override_get_db
    override_sirius_sdk()

    # Emulate websocket
    client = TestClient(app)
    agent_did, agent_verkey, agent_secret = random_me
    agent_crypto = MediatorCrypto(agent_verkey, agent_secret)
    with client.websocket_connect("/") as websocket:
        """Process 0160 aries protocol"""

        # Agent acts as inviter, initialize pairwise
        invitation = Invitation(label='Agent', recipient_keys=[agent_verkey], endpoint=WS_ENDPOINT)
        websocket.send_bytes(json.dumps(invitation).encode())

        # Receive answer
        enc_msg = websocket.receive_bytes()
        payload, sender_vk, recip_vk = unpack_message(enc_message=enc_msg, my_verkey=agent_verkey, my_sigkey=agent_secret)
        assert sender_vk == KEYPAIR[0]
        assert recip_vk == agent_verkey

        # Check reply is ConnRequest
        ok, request = restore_message_instance(json.loads(payload))
        assert ok and isinstance(request, sirius_sdk.aries_rfc.ConnRequest)
        request.validate()
        their_did, their_vk, their_endpoint_address, their_routing_keys = request.extract_their_info()
        services = request.did_doc.get('service', [])
        assert any([s['type'] == MEDIATOR_SERVICE_TYPE for s in services])

        # Build connection response
        did_doc = ConnProtocolMessage.build_did_doc(agent_did, agent_verkey, WS_ENDPOINT)
        did_doc_extra = {'service': did_doc['service']}
        did_doc_extra['service'].append({
            "id": 'did:peer:' + agent_did + ";indy",
            "type": FCM_SERVICE_TYPE,
            "recipientKeys": [],
            "serviceEndpoint": random_fcm_device_id,
        })
        assert 2 == len(did_doc_extra['service'])

        response = ConnResponse(
            did=agent_did,
            verkey=agent_verkey,
            endpoint=WS_ENDPOINT,
            did_doc_extra=did_doc_extra
        )
        if request.please_ack:
            response.thread_id = request.ack_message_id
        asyncio.get_event_loop().run_until_complete(response.sign_connection(agent_crypto, agent_verkey))
        # According 0160 aries_rfc prefer to check connection with Ack messages
        response.please_ack = True

        # Send signed response to Mediator
        packed = pack_message(
            message=json.dumps(response),
            to_verkeys=[their_vk],
            from_verkey=agent_verkey,
            from_sigkey=agent_secret
        )
        websocket.send_bytes(packed)

        # Receive answer
        enc_msg = websocket.receive_bytes()
        payload, sender_vk, recip_vk = unpack_message(
            enc_message=enc_msg, my_verkey=agent_verkey, my_sigkey=agent_secret
        )
        ok, ack = restore_message_instance(json.loads(payload))

        # check Pairwise was successfully established
        assert ok and isinstance(ack, sirius_sdk.aries_rfc.Ack)
        assert sender_vk == KEYPAIR[0]
        assert recip_vk == agent_verkey

        # Check agent record is stored in database
        sleep(3)  # give websocket time to fire db records
        agent = asyncio.get_event_loop().run_until_complete(load_agent(test_database, agent_did))
        assert agent is not None
        assert agent['verkey'] == agent_verkey
        assert agent['id'] is not None
        assert agent['metadata'] is not None
        assert agent['fcm_device_id'] == random_fcm_device_id
        # Check endpoint exists
        endpoint_uid = hashlib.sha256(agent_verkey.encode('utf-8')).hexdigest()
        endpoint = asyncio.get_event_loop().run_until_complete(load_endpoint(test_database, endpoint_uid))
        assert endpoint is not None
        assert endpoint['redis_pub_sub'] is not None
        assert endpoint['agent_id'] == agent['id']
        assert endpoint['verkey'] == agent_verkey
        assert endpoint['uid']


def test_trust_ping(random_me: (str, str, str)):
    """Check TrustPing communication for earlier established P2P
    """
    # Override original database with test one
    app.dependency_overrides[get_db] = override_get_db
    override_sirius_sdk()

    # Emulate TrustPing communication
    client = TestClient(app)
    did, verkey, secret = random_me
    p2p = P2PConnection(my_keys=(verkey, secret), their_verkey=KEYPAIR[0])
    with client.websocket_connect("/") as websocket:
        ping = Ping(response_requested=True)
        packed = p2p.pack(ping)
        websocket.send_bytes(packed)
        packed = websocket.receive_bytes()
        msg = p2p.unpack(enc_message=packed)
        assert 'ping_response' in msg['@type']
        assert msg['~thread']['thid'] == ping.id
