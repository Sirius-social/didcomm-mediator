import json
import asyncio
import hashlib
from time import sleep
from urllib.parse import urlparse

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
from app.settings import ROUTER_PATH
from app.dependencies import get_db
from app.settings import KEYPAIR, FCM_SERVICE_TYPE, MEDIATOR_SERVICE_TYPE, DID, \
    ENDPOINTS_PATH_PREFIX, WS_PATH_PREFIX, WEBROOT, LONG_POLLING_PATH_PREFIX
from app.core.crypto import MediatorCrypto
from app.utils import build_invitation
from app.db.crud import load_agent, load_endpoint_via_verkey

from .helpers import override_sirius_sdk, override_get_db


WS_ENDPOINT = 'ws://'

client = TestClient(app)
app.dependency_overrides[get_db] = override_get_db


def test_p2p_protocols(test_database: Database, random_me: (str, str, str), random_fcm_device_id: str):
    """Check step-by step AriesRFC 0160 while agent establish P2P with Mediator
    """
    # Override original database with test one
    override_sirius_sdk()

    # Emulate websocket
    agent_did, agent_verkey, agent_secret = random_me
    agent_crypto = MediatorCrypto(agent_verkey, agent_secret)
    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
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
        assert 3 == len(mediator_services)
        assert any([s['type'] == MEDIATOR_SERVICE_TYPE for s in mediator_services])
        for srv in mediator_services:
            assert DID in str(srv)
            if srv['type'] == MEDIATOR_SERVICE_TYPE:
                assert '?endpoint=' in srv['serviceEndpoint']
                url_parts = urlparse(srv['serviceEndpoint'])
                assert url_parts.path.startswith(f'/{WS_PATH_PREFIX}') or url_parts.path.startswith(f'/{LONG_POLLING_PATH_PREFIX}')

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
        endpoint = asyncio.get_event_loop().run_until_complete(load_endpoint_via_verkey(test_database, agent_verkey))
        assert endpoint is not None
        assert endpoint['redis_pub_sub'] is not None
        assert endpoint['redis_pub_sub'].count('redis://') == 1, 'Regression test'
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
        assert endpoint['uid'] in grant['endpoint']
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
        assert key1 in str(upd_keys)
        assert key2 in str(upd_keys)
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
        assert len(list_res['keys']) == 1
        assert key1 not in str(list_res['keys'])
        assert key2 in str(list_res['keys'])
        # Mediate request again
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
        assert len(grant['routing_keys']) == 1  # mediator key
        assert connection_key in grant['routing_keys'][0]
        assert ROUTER_PATH in grant['endpoint'], 'Router endpoint expected!'


def test_trust_ping(random_me: (str, str, str)):
    """Check TrustPing communication for earlier established P2P
    """
    # Override original database with test one
    override_sirius_sdk()

    # Emulate TrustPing communication
    did, verkey, secret = random_me
    p2p = P2PConnection(my_keys=(verkey, secret), their_verkey=KEYPAIR[0])
    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        ping = Ping(response_requested=True)
        packed = p2p.pack(ping)
        websocket.send_bytes(packed)
        packed = websocket.receive_bytes()
        msg = p2p.unpack(enc_message=packed)
        assert 'ping_response' in msg['@type']
        assert msg['~thread']['thid'] == ping.id


def test_problem_reports(random_me: (str, str, str), random_their: (str, str, str)):
    """Validate Problem Reports"""

    # Override original database with test one
    override_sirius_sdk()

    # Emulate TrustPing communication
    did, verkey, secret = random_me
    their_did, their_verkey, their_secret = random_their

    p2p = P2PConnection(my_keys=(verkey, secret), their_verkey=KEYPAIR[0])
    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        req = MediateRequest()
        packed = p2p.pack(req)
        websocket.send_bytes(packed)
        packed = websocket.receive_bytes()
        msg = p2p.unpack(enc_message=packed)
        assert 'problem_report' in msg['@type']
        assert 'explain' in msg


def test_same_endpoint_for_different_verkeys(random_me: (str, str, str)):
    """Check Every time Client change self Verkey, Mediator will not change endpoint
    """
    # Override original database with test one
    override_sirius_sdk()

    # Emulate communication
    mediator_invitation = build_invitation()
    did, verkey1, secret1 = random_me
    verkey2_b, secret2_b = sirius_sdk.encryption.ed25519.create_keypair()
    verkey2, secret2 = sirius_sdk.encryption.bytes_to_b58(verkey2_b), sirius_sdk.encryption.bytes_to_b58(secret2_b)
    their_verkey = mediator_invitation['recipientKeys'][0]

    allocated_mediator_endpoints = []  # websocket address for pulling events from endpoint
    allocated_http_endpoints = []  # granted endpoint
    _, mediator_invitation = restore_message_instance(build_invitation())
    their_verkey = mediator_invitation['recipientKeys'][0]

    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        """Process 0160 aries protocol 2 times for every verkey"""

        for verkey, secret in [(verkey1, secret1), (verkey2, secret2)]:
            # Build Connection request
            request = ConnRequest(
                label='Test Agent',
                did=did,
                verkey=verkey,
                endpoint=WS_ENDPOINT,
            )
            # Send signed response to Mediator
            websocket.send_bytes(
                pack_message(
                    message=json.dumps(request), to_verkeys=[their_verkey], from_verkey=verkey, from_sigkey=secret
                )
            )
            # Receive answer
            enc_msg = websocket.receive_bytes()
            payload, sender_vk, recip_vk = unpack_message(
                enc_message=enc_msg, my_verkey=verkey, my_sigkey=secret
            )
            _, response = restore_message_instance(json.loads(payload))

            # Check mediator endpoints and services
            success = asyncio.get_event_loop().run_until_complete(response.verify_connection(sirius_sdk.Crypto))
            assert success is True
            mediator_services = response.did_doc['service']
            for service in mediator_services:
                if service['type'] == MEDIATOR_SERVICE_TYPE:
                    allocated_mediator_endpoints.append(service['serviceEndpoint'])
            # Notify connection is OK
            ack = Ack(thread_id=response.ack_message_id, status=Status.OK)
            packed = pack_message(
                message=json.dumps(ack),
                to_verkeys=[their_verkey],
                from_verkey=verkey,
                from_sigkey=secret
            )
            websocket.send_bytes(packed)
            # Store endpoint granted via route-coordination protocol
            grant_request = MediateRequest()
            websocket.send_bytes(pack_message(
                message=json.dumps(grant_request),
                to_verkeys=[their_verkey],
                from_verkey=verkey,
                from_sigkey=secret
            ))
            enc_msg = websocket.receive_bytes()
            payload, sender_vk, recip_vk = unpack_message(
                enc_message=enc_msg, my_verkey=verkey, my_sigkey=secret
            )
            _, grant_response = restore_message_instance(json.loads(payload))
            allocated_http_endpoints.append(grant_response['endpoint'])

        # Check all values are equal
        assert len(allocated_mediator_endpoints) == 4
        assert allocated_mediator_endpoints[0] == allocated_mediator_endpoints[2]
        assert allocated_mediator_endpoints[1] == allocated_mediator_endpoints[3]
        assert len(allocated_http_endpoints) == 2
        assert allocated_http_endpoints[0] == allocated_http_endpoints[1]
