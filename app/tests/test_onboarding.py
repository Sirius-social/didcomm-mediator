import json
import asyncio
import hashlib
from time import sleep

import sirius_sdk
from databases import Database
from fastapi.testclient import TestClient
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol.messages import Invitation, \
    ConnResponse, ConnProtocolMessage, ConnRequest
from sirius_sdk.encryption import P2PConnection, unpack_message, pack_message
from sirius_sdk.agent.aries_rfc.feature_0048_trust_ping.messages import Ping
from sirius_sdk.agent.aries_rfc.feature_0015_acks.messages import Ack, Status
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import MediateRequest, \
    MediateGrant, KeylistUpdate, KeylistUpdateResponce, KeylistAddAction, KeylistRemoveAction, KeylistQuery, Keylist
from sirius_sdk.messaging import restore_message_instance

from app.main import app
from app.dependencies import get_db
from app.settings import KEYPAIR, FCM_SERVICE_TYPE, MEDIATOR_SERVICE_TYPE, DID, ENDPOINTS_PATH_PREFIX
from app.core.crypto import MediatorCrypto
from app.utils import build_invitation
from app.db.crud import load_agent, load_endpoint

from .helpers import override_sirius_sdk, override_get_db


WS_ENDPOINT = 'ws://'


def test_p2p_protocols(test_database: Database, random_me: (str, str, str), random_fcm_device_id: str):
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
        ok, mediator_invitation = restore_message_instance(build_invitation())
        assert ok
        assert isinstance(mediator_invitation, Invitation)
        mediator_invitation.validate()

        connection_key = mediator_invitation.recipient_keys[0]
        mediator_endpoint = sirius_sdk.TheirEndpoint(
            endpoint=mediator_invitation.endpoint,
            verkey=connection_key
        )

        # Build connection response
        did_doc = ConnRequest.build_did_doc(agent_did, agent_verkey, WS_ENDPOINT)
        did_doc_extra = {'service': did_doc['service']}
        did_doc_extra['service'].append({
            "id": 'did:peer:' + agent_did + ";indy",
            "type": FCM_SERVICE_TYPE,
            "recipientKeys": [],
            "priority": 1,
            "serviceEndpoint": random_fcm_device_id,
        })
        assert 2 == len(did_doc_extra['service'])

        # Build Connection request
        request = ConnRequest(
            label='Test Agent',
            did=agent_did,
            verkey=agent_verkey,
            endpoint=WS_ENDPOINT,
            did_doc_extra=did_doc
        )

        # Send signed response to Mediator
        packed = pack_message(
            message=json.dumps(request),
            to_verkeys=[connection_key],
            from_verkey=agent_verkey,
            from_sigkey=agent_secret
        )
        websocket.send_bytes(packed)

        # Receive answer
        enc_msg = websocket.receive_bytes()
        payload, sender_vk, recip_vk = unpack_message(
            enc_message=enc_msg, my_verkey=agent_verkey, my_sigkey=agent_secret
        )
        ok, response = restore_message_instance(json.loads(payload))

        # Check reply is valid ConnResponse
        assert ok and isinstance(response, ConnResponse)
        assert sender_vk == KEYPAIR[0]
        assert recip_vk == agent_verkey
        success = asyncio.get_event_loop().run_until_complete(response.verify_connection(sirius_sdk.Crypto))
        assert success is True
        response.validate()

        # Check mediator endpoints and services
        mediator_did_doc = response.did_doc
        mediator_services = mediator_did_doc['service']
        assert 2 == len(mediator_services)
        assert any([s['type'] == MEDIATOR_SERVICE_TYPE for s in mediator_services])
        for srv in mediator_services:
            assert DID in str(srv)
            if srv['type'] == MEDIATOR_SERVICE_TYPE:
                assert '?endpoint=' in srv['serviceEndpoint']

        # Notify connection is OK
        ack = Ack(thread_id=response.ack_message_id, status=Status.OK)
        packed = pack_message(
            message=json.dumps(ack),
            to_verkeys=[connection_key],
            from_verkey=agent_verkey,
            from_sigkey=agent_secret
        )
        websocket.send_bytes(packed)

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
        assert endpoint['fcm_device_id'] == random_fcm_device_id
        assert endpoint['uid']

        # !!!!!!! Emulate Route Coordination !!!!!!!
        their_vk = connection_key
        req = MediateRequest()
        packed = pack_message(
            message=json.dumps(req),
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
        ok, grant = restore_message_instance(json.loads(payload))
        assert ok is True and isinstance(grant, MediateGrant)
        assert 'endpoint' in grant.keys()
        assert f'/{ENDPOINTS_PATH_PREFIX}/' in grant['endpoint']
        assert ENDPOINTS_PATH_PREFIX
        assert 'routing_keys' in grant.keys()
        # update keys
        key1 = 'z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH'
        key2 = 'XXXkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvZZZ'
        req = KeylistUpdate(
            endpoint=grant['endpoint'],
            updates=[
                KeylistAddAction(recipient_key=f'did:key:{key1}'),
                KeylistAddAction(recipient_key=f'{key2}'),
            ]
        )
        packed = pack_message(
            message=json.dumps(req),
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
        ok, upd_res = restore_message_instance(json.loads(payload))
        assert ok is True and isinstance(upd_res, KeylistUpdateResponce)
        assert 'updated' in upd_res.keys()
        assert 2 == len(upd_res['updated'])
        upd_keys = [item['recipient_key'] for item in upd_res['updated']]
        assert key1 in upd_keys
        assert key2 in upd_keys
        # Remove key
        req = KeylistUpdate(
            endpoint=grant['endpoint'],
            updates=[
                KeylistRemoveAction(recipient_key=f'did:key:{key1}'),
            ]
        )
        packed = pack_message(
            message=json.dumps(req),
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
        ok, upd_res = restore_message_instance(json.loads(payload))
        assert ok is True and isinstance(upd_res, KeylistUpdateResponce)
        assert 'updated' in upd_res.keys()
        assert 1 == len(upd_res['updated'])
        assert key1 in str(upd_res['updated'])
        # Query key list
        req = KeylistQuery()
        packed = pack_message(
            message=json.dumps(req),
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
        ok, list_res = restore_message_instance(json.loads(payload))
        assert ok is True and isinstance(list_res, Keylist)


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
