import json
import urllib.parse
import uuid
import asyncio
from time import sleep

import pytest
from databases import Database
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sirius_sdk.encryption import unpack_message, create_keypair, bytes_to_b58, pack_message

import settings
from app.main import app
from app.dependencies import get_db
from app.utils import build_endpoint_url
from app.db.crud import ensure_endpoint_exists, load_endpoint, add_routing_key
from app.settings import WS_PATH_PREFIX, WEBROOT, LONG_POLLING_PATH_PREFIX
from app.core.redis import AsyncRedisChannel
from app.core.forward import FORWARD, forward_wired
from app.routers.mediator_scenarios import URI_QUEUE_TRANSPORT

from .helpers import override_get_db, override_sirius_sdk
from .emulators import DIDCommRecipient as ClientEmulator
from app.utils import build_invitation


client = TestClient(app)
app.dependency_overrides[get_db] = override_get_db


def test_delivery_via_websocket(test_database: Database, random_me: (str, str, str), random_endpoint_uid: str):

    """Check any content posted to endpoint is delivered to Client websocket connection
    """
    content = b'{"protected": "eyJlbmMiOiAieGNoYWNoYTIwcG9seTEzMDVfaWV0ZiIsICJ0eXAiOiAiSldNLzEuMCIsICJhbGciOiAiQXV0aGNyeXB0IiwgInJlY2lwaWVudHMiOiBbeyJlbmNyeXB0ZWRfa2V5IjogInBKcW1xQS1IVWR6WTNWcFFTb2dySGx4WTgyRnc3Tl84YTFCSmtHU2VMT014VUlwT0RQWTZsMVVsaVVvOXFwS0giLCAiaGVhZGVyIjogeyJraWQiOiAiM1ZxZ2ZUcDZRNFZlRjhLWTdlVHVXRFZBWmFmRDJrVmNpb0R2NzZLR0xtZ0QiLCAic2VuZGVyIjogIjRlYzhBeFRHcWtxamd5NHlVdDF2a0poeWlYZlNUUHo1bTRKQjk1cGZSMG1JVW9KajAwWmswNmUyUEVDdUxJYmRDck8xeTM5LUhGTG5NdW5YQVJZWk5rZ2pyYV8wYTBQODJpbVdNcWNHc1FqaFd0QUhOcUw1OGNkUUYwYz0iLCAiaXYiOiAiVU1PM2o1ZHZwQnFMb2Rvd3V0c244WEMzTkVqSWJLb2oifX1dfQ==", "iv": "MchkHF2M-4hneeUJ", "ciphertext": "UgcdsV-0rIkP25eJuRSROOuqiTEXp4NToKjPMmqqtJs-Ih1b5t3EEbrrHxeSfPsHtlO6J4OqA1jc5uuD3aNssUyLug==", "tag": "sQD8qgJoTrRoyQKPeCSBlQ=="}'
    content_type = 'application/ssi-agent-wire'

    agent_did, agent_verkey, agent_secret = random_me
    redis_pub_sub = 'redis://redis1/%s' % uuid.uuid4().hex

    asyncio.get_event_loop().run_until_complete(ensure_endpoint_exists(
        db=test_database, uid=random_endpoint_uid, redis_pub_sub=redis_pub_sub,
        agent_id=agent_did, verkey=agent_verkey
    ))
    with client.websocket_connect(f"/{WS_PATH_PREFIX}?endpoint={random_endpoint_uid}") as websocket:
        sleep(3)  # give websocket timeout to accept connection
        response = client.post(
            build_endpoint_url(random_endpoint_uid),
            headers={"Content-Type": content_type},
            data=content,
        )
        assert response.status_code == 202

        enc_msg = websocket.receive_json()
        assert enc_msg == json.loads(content.decode())

        # Close websocket
        websocket.close()
        sleep(3)  # give websocket timeout to accept connection
        url = build_endpoint_url(random_endpoint_uid)
        response = client.post(
            url,
            headers={"Content-Type": content_type},
            data=content,
        )
        assert response.status_code == 410


def test_delivery_json_via_websocket(test_database: Database, random_me: (str, str, str), random_endpoint_uid: str):
    """Check JSON content posted to endpoint is delivered to Client websocket connection
    """
    content_json = {'key1': 'value', 'key2': 123}
    content = json.dumps(content_json).encode()
    content_type = 'application/json'

    agent_did, agent_verkey, agent_secret = random_me
    redis_pub_sub = 'redis://redis1/%s' % uuid.uuid4().hex

    asyncio.get_event_loop().run_until_complete(ensure_endpoint_exists(
        db=test_database, uid=random_endpoint_uid, redis_pub_sub=redis_pub_sub,
        agent_id=agent_did, verkey=agent_verkey
    ))
    with client.websocket_connect(f"/{WS_PATH_PREFIX}?endpoint={random_endpoint_uid}") as websocket:
        sleep(3)  # give websocket timeout to accept connection
        response = client.post(
            build_endpoint_url(random_endpoint_uid),
            headers={"Content-Type": content_type},
            data=content,
        )
        assert response.status_code == 202

        enc_msg = websocket.receive_json()
        assert enc_msg == content_json


def test_unsupported_content_type(test_database: Database, random_me: (str, str, str), random_endpoint_uid: str):
    """Check unsupported content-type will raise http error status"""
    content = b'{"protected": "eyJlbmMiOiAieGNoYWNoYTIwcG9seTEzMDVfaWV0ZiIsICJ0eXAiOiAiSldNLzEuMCIsICJhbGciOiAiQXV0aGNyeXB0IiwgInJlY2lwaWVudHMiOiBbeyJlbmNyeXB0ZWRfa2V5IjogInBKcW1xQS1IVWR6WTNWcFFTb2dySGx4WTgyRnc3Tl84YTFCSmtHU2VMT014VUlwT0RQWTZsMVVsaVVvOXFwS0giLCAiaGVhZGVyIjogeyJraWQiOiAiM1ZxZ2ZUcDZRNFZlRjhLWTdlVHVXRFZBWmFmRDJrVmNpb0R2NzZLR0xtZ0QiLCAic2VuZGVyIjogIjRlYzhBeFRHcWtxamd5NHlVdDF2a0poeWlYZlNUUHo1bTRKQjk1cGZSMG1JVW9KajAwWmswNmUyUEVDdUxJYmRDck8xeTM5LUhGTG5NdW5YQVJZWk5rZ2pyYV8wYTBQODJpbVdNcWNHc1FqaFd0QUhOcUw1OGNkUUYwYz0iLCAiaXYiOiAiVU1PM2o1ZHZwQnFMb2Rvd3V0c244WEMzTkVqSWJLb2oifX1dfQ==", "iv": "MchkHF2M-4hneeUJ", "ciphertext": "UgcdsV-0rIkP25eJuRSROOuqiTEXp4NToKjPMmqqtJs-Ih1b5t3EEbrrHxeSfPsHtlO6J4OqA1jc5uuD3aNssUyLug==", "tag": "sQD8qgJoTrRoyQKPeCSBlQ=="}'
    content_type = 'application/invalid-type'

    agent_did, agent_verkey, agent_secret = random_me
    redis_pub_sub = 'redis://redis1/%s' % uuid.uuid4().hex

    asyncio.get_event_loop().run_until_complete(ensure_endpoint_exists(
        db=test_database, uid=random_endpoint_uid, redis_pub_sub=redis_pub_sub,
        agent_id=agent_did, verkey=agent_verkey
    ))
    response = client.post(
        build_endpoint_url(random_endpoint_uid),
        headers={"Content-Type": content_type},
        data=content,
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_delivery_via_fcm(test_database: Database, random_me: (str, str, str), random_endpoint_uid: str):
    """Check unsupported content-type will raise http error status"""
    content = b'{"protected": "eyJlbmMiOiAieGNoYWNoYTIwcG9seTEzMDVfaWV0ZiIsICJ0eXAiOiAiSldNLzEuMCIsICJhbGciOiAiQXV0aGNyeXB0IiwgInJlY2lwaWVudHMiOiBbeyJlbmNyeXB0ZWRfa2V5IjogInBKcW1xQS1IVWR6WTNWcFFTb2dySGx4WTgyRnc3Tl84YTFCSmtHU2VMT014VUlwT0RQWTZsMVVsaVVvOXFwS0giLCAiaGVhZGVyIjogeyJraWQiOiAiM1ZxZ2ZUcDZRNFZlRjhLWTdlVHVXRFZBWmFmRDJrVmNpb0R2NzZLR0xtZ0QiLCAic2VuZGVyIjogIjRlYzhBeFRHcWtxamd5NHlVdDF2a0poeWlYZlNUUHo1bTRKQjk1cGZSMG1JVW9KajAwWmswNmUyUEVDdUxJYmRDck8xeTM5LUhGTG5NdW5YQVJZWk5rZ2pyYV8wYTBQODJpbVdNcWNHc1FqaFd0QUhOcUw1OGNkUUYwYz0iLCAiaXYiOiAiVU1PM2o1ZHZwQnFMb2Rvd3V0c244WEMzTkVqSWJLb2oifX1dfQ==", "iv": "MchkHF2M-4hneeUJ", "ciphertext": "UgcdsV-0rIkP25eJuRSROOuqiTEXp4NToKjPMmqqtJs-Ih1b5t3EEbrrHxeSfPsHtlO6J4OqA1jc5uuD3aNssUyLug==", "tag": "sQD8qgJoTrRoyQKPeCSBlQ=="}'
    content_type = 'application/ssi-agent-wire'

    agent_did, agent_verkey, agent_secret = random_me
    fcm_device_id = 'redis://redis1/%s' % uuid.uuid4().hex

    await ensure_endpoint_exists(
        db=test_database, uid=random_endpoint_uid, fcm_device_id=fcm_device_id,
        agent_id=agent_did, verkey=agent_verkey
    )

    received_fcm_msgs = []

    async def read_fcm(address: str):
        ch = AsyncRedisChannel(fcm_device_id)
        while True:
            ok, msg = await ch.read(timeout=1000)
            if ok:
                received_fcm_msgs.append(msg)
            else:
                return

    fut = asyncio.ensure_future(read_fcm(fcm_device_id))
    await asyncio.sleep(3)

    async with AsyncClient(app=app, base_url=WEBROOT) as cli:
        response = await cli.post(
            build_endpoint_url(random_endpoint_uid),
            headers={"Content-Type": content_type},
            data=content,
        )
        assert response.status_code == 202

    fut.cancel()
    assert len(received_fcm_msgs) == 1
    fcm_msg = received_fcm_msgs[0]
    assert fcm_msg == json.loads(content.decode())


@pytest.mark.asyncio
async def test_delivery_via_long_polling(test_database: Database, random_me: (str, str, str), random_endpoint_uid: str):
    """Check long polling delivery mechanism"""
    content = b'{"protected": "eyJlbmMiOiAieGNoYWNoYTIwcG9seTEzMDVfaWV0ZiIsICJ0eXAiOiAiSldNLzEuMCIsICJhbGciOiAiQXV0aGNyeXB0IiwgInJlY2lwaWVudHMiOiBbeyJlbmNyeXB0ZWRfa2V5IjogInBKcW1xQS1IVWR6WTNWcFFTb2dySGx4WTgyRnc3Tl84YTFCSmtHU2VMT014VUlwT0RQWTZsMVVsaVVvOXFwS0giLCAiaGVhZGVyIjogeyJraWQiOiAiM1ZxZ2ZUcDZRNFZlRjhLWTdlVHVXRFZBWmFmRDJrVmNpb0R2NzZLR0xtZ0QiLCAic2VuZGVyIjogIjRlYzhBeFRHcWtxamd5NHlVdDF2a0poeWlYZlNUUHo1bTRKQjk1cGZSMG1JVW9KajAwWmswNmUyUEVDdUxJYmRDck8xeTM5LUhGTG5NdW5YQVJZWk5rZ2pyYV8wYTBQODJpbVdNcWNHc1FqaFd0QUhOcUw1OGNkUUYwYz0iLCAiaXYiOiAiVU1PM2o1ZHZwQnFMb2Rvd3V0c244WEMzTkVqSWJLb2oifX1dfQ==", "iv": "MchkHF2M-4hneeUJ", "ciphertext": "UgcdsV-0rIkP25eJuRSROOuqiTEXp4NToKjPMmqqtJs-Ih1b5t3EEbrrHxeSfPsHtlO6J4OqA1jc5uuD3aNssUyLug==", "tag": "sQD8qgJoTrRoyQKPeCSBlQ=="}'
    content_type = 'application/ssi-agent-wire'

    agent_did, agent_verkey, agent_secret = random_me
    redis_pub_sub = 'redis://redis1/%s' % uuid.uuid4().hex

    await ensure_endpoint_exists(
        db=test_database, uid=random_endpoint_uid,
        agent_id=agent_did, verkey=agent_verkey, redis_pub_sub=redis_pub_sub
    )

    received_lines = []

    async def read_lines():
        async with AsyncClient(app=app, base_url=WEBROOT) as cli:
            async with cli.stream('GET', f"/{LONG_POLLING_PATH_PREFIX}?endpoint={random_endpoint_uid}") as response:
                async for chunk in response.aiter_text():
                    received_lines.append(chunk)

    send_count = 2
    fut = asyncio.ensure_future(read_lines())
    await asyncio.sleep(5)
    try:
        async with AsyncClient(app=app, base_url=WEBROOT) as cli:
            for n in range(send_count):
                response = await cli.post(
                    build_endpoint_url(random_endpoint_uid),
                    headers={"Content-Type": content_type},
                    data=content,
                )
                assert response.status_code == 202
    finally:
        fut.cancel()
    await asyncio.sleep(3)


def test_delivery_with_queue_route_if_group_empty(random_me: (str, str, str)):
    """Check delivery with Queue-Route DIDComm extension

        - details: https://github.com/decentralized-identity/didcomm-messaging/blob/master/extensions/return_route/main.md#queue-transport
    """
    content = b'{"protected": "eyJlbmMiOiAieGNoYWNoYTIwcG9seTEzMDVfaWV0ZiIsICJ0eXAiOiAiSldNLzEuMCIsICJhbGciOiAiQXV0aGNyeXB0IiwgInJlY2lwaWVudHMiOiBbeyJlbmNyeXB0ZWRfa2V5IjogInBKcW1xQS1IVWR6WTNWcFFTb2dySGx4WTgyRnc3Tl84YTFCSmtHU2VMT014VUlwT0RQWTZsMVVsaVVvOXFwS0giLCAiaGVhZGVyIjogeyJraWQiOiAiM1ZxZ2ZUcDZRNFZlRjhLWTdlVHVXRFZBWmFmRDJrVmNpb0R2NzZLR0xtZ0QiLCAic2VuZGVyIjogIjRlYzhBeFRHcWtxamd5NHlVdDF2a0poeWlYZlNUUHo1bTRKQjk1cGZSMG1JVW9KajAwWmswNmUyUEVDdUxJYmRDck8xeTM5LUhGTG5NdW5YQVJZWk5rZ2pyYV8wYTBQODJpbVdNcWNHc1FqaFd0QUhOcUw1OGNkUUYwYz0iLCAiaXYiOiAiVU1PM2o1ZHZwQnFMb2Rvd3V0c244WEMzTkVqSWJLb2oifX1dfQ==", "iv": "MchkHF2M-4hneeUJ", "ciphertext": "UgcdsV-0rIkP25eJuRSROOuqiTEXp4NToKjPMmqqtJs-Ih1b5t3EEbrrHxeSfPsHtlO6J4OqA1jc5uuD3aNssUyLug==", "tag": "sQD8qgJoTrRoyQKPeCSBlQ=="}'
    content_type = 'application/didcomm-envelope-enc'

    override_sirius_sdk()

    agent_did, agent_verkey, agent_secret = random_me

    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        try:
            sleep(3)  # give websocket timeout to accept connection
            cli = ClientEmulator(
                transport=websocket, mediator_invitation=build_invitation(),
                agent_did=agent_did, agent_verkey=agent_verkey, agent_secret=agent_secret,
                ####################
                group_id=None
                ###################
            )
            # 1. Establish connection with Mediator
            mediator_did_doc = cli.connect(endpoint=URI_QUEUE_TRANSPORT)
            # 2. Allocate endpoint
            mediate_grant = cli.mediate_grant()
            # 3. Post wired via endpoint
            response = client.post(
                mediate_grant['endpoint'],
                headers={"Content-Type": content_type},
                data=content
            )
            assert response.status_code == 410
            # wired_actual = websocket.receive_json()
            # wired_expected = json.loads(content.decode())
            # assert wired_expected == wired_actual
        finally:
            websocket.close()


def test_delivery_when_redis_server_fail(test_database: Database, random_me: (str, str, str), random_endpoint_uid: str):
    """Check Push service will reconfigure endpoint to new redis instance if old address is unreachable
    """
    content = b'{"protected": "eyJlbmMiOiAieGNoYWNoYTIwcG9seTEzMDVfaWV0ZiIsICJ0eXAiOiAiSldNLzEuMCIsICJhbGciOiAiQXV0aGNyeXB0IiwgInJlY2lwaWVudHMiOiBbeyJlbmNyeXB0ZWRfa2V5IjogInBKcW1xQS1IVWR6WTNWcFFTb2dySGx4WTgyRnc3Tl84YTFCSmtHU2VMT014VUlwT0RQWTZsMVVsaVVvOXFwS0giLCAiaGVhZGVyIjogeyJraWQiOiAiM1ZxZ2ZUcDZRNFZlRjhLWTdlVHVXRFZBWmFmRDJrVmNpb0R2NzZLR0xtZ0QiLCAic2VuZGVyIjogIjRlYzhBeFRHcWtxamd5NHlVdDF2a0poeWlYZlNUUHo1bTRKQjk1cGZSMG1JVW9KajAwWmswNmUyUEVDdUxJYmRDck8xeTM5LUhGTG5NdW5YQVJZWk5rZ2pyYV8wYTBQODJpbVdNcWNHc1FqaFd0QUhOcUw1OGNkUUYwYz0iLCAiaXYiOiAiVU1PM2o1ZHZwQnFMb2Rvd3V0c244WEMzTkVqSWJLb2oifX1dfQ==", "iv": "MchkHF2M-4hneeUJ", "ciphertext": "UgcdsV-0rIkP25eJuRSROOuqiTEXp4NToKjPMmqqtJs-Ih1b5t3EEbrrHxeSfPsHtlO6J4OqA1jc5uuD3aNssUyLug==", "tag": "sQD8qgJoTrRoyQKPeCSBlQ=="}'
    content_type = 'application/ssi-agent-wire'

    agent_did, agent_verkey, agent_secret = random_me
    unreachable_redis_pub_sub = 'redis://unreachable/%s' % uuid.uuid4().hex

    asyncio.get_event_loop().run_until_complete(ensure_endpoint_exists(
        db=test_database, uid=random_endpoint_uid, redis_pub_sub=unreachable_redis_pub_sub,
        agent_id=agent_did, verkey=agent_verkey
    ))
    response = client.post(
        build_endpoint_url(random_endpoint_uid),
        headers={"Content-Type": content_type},
        data=content,
    )
    assert response.status_code == 410

    # Check new redis pub-sub was stored
    endpoint = asyncio.get_event_loop().run_until_complete(load_endpoint(db=test_database, uid=random_endpoint_uid))
    assert endpoint['redis_pub_sub'] != unreachable_redis_pub_sub
    assert 'redis://redis1/' in endpoint['redis_pub_sub'] or 'redis://redis2/' in endpoint['redis_pub_sub']


def test_forward_msg(test_database: Database, random_me: (str, str, str), random_endpoint_uid: str, random_keys: (str, str)):
    expected_msg = {'message': 'Hello!'}
    content_type = 'application/didcomm-envelope-enc'

    agent_did, agent_verkey, agent_secret = random_me
    redis_pub_sub = 'redis://redis1/%s' % uuid.uuid4().hex
    routing_key, routing_secret = random_keys

    asyncio.get_event_loop().run_until_complete(ensure_endpoint_exists(
        db=test_database, uid=random_endpoint_uid, redis_pub_sub=redis_pub_sub,
        agent_id=agent_did, verkey=agent_verkey
    ))
    asyncio.get_event_loop().run_until_complete(add_routing_key(
        db=test_database, endpoint_uid=random_endpoint_uid, key=routing_key
    ))
    mediator_invitation = build_invitation()
    mediator_vk = mediator_invitation['recipientKeys'][0]

    with client.websocket_connect(f"/{WS_PATH_PREFIX}?endpoint={random_endpoint_uid}") as websocket:
        sleep(3)  # give websocket timeout to accept connection
        sender_vk, sender_sk = create_keypair()
        sender_vk, sender_sk = bytes_to_b58(sender_vk), bytes_to_b58(sender_sk)
        wired = pack_message(json.dumps(expected_msg), to_verkeys=[agent_verkey], from_verkey=sender_vk, from_sigkey=sender_sk)
        fwd = forward_wired(
            payload=wired,
            their_vk=agent_verkey,
            routing_keys=[routing_key, mediator_vk]
        )
        response = client.post(
            settings.ROUTER_PATH,
            headers={"Content-Type": content_type},
            data=fwd,
        )
        assert response.status_code == 202

        enc_msg = websocket.receive_json()
        fwd, sender_vk, recp_vk = unpack_message(enc_msg, my_verkey=routing_key, my_sigkey=routing_secret)
        fwd = json.loads(fwd)
        assert fwd['@type'] == FORWARD
        assert fwd['to'] == agent_verkey
        enc_msg = json.dumps(fwd['msg']).encode()
        unpacked, sender_vk, recp_vk = unpack_message(enc_msg, my_verkey=agent_verkey, my_sigkey=agent_secret)
        actual_msg = json.loads(unpacked)
        assert expected_msg == actual_msg


def test_pass_group_id_via_diddoc(random_me: (str, str, str)):

    override_sirius_sdk()
    agent_did, agent_verkey, agent_secret = random_me
    group_id = 'group-id-' + uuid.uuid4().hex

    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        try:
            sleep(3)  # give websocket timeout to accept connection
            cli = ClientEmulator(
                transport=websocket, mediator_invitation=build_invitation(),
                agent_did=agent_did, agent_verkey=agent_verkey, agent_secret=agent_secret, group_id=group_id
            )
            # 1. Establish connection with Mediator
            mediator_did_doc = cli.connect(endpoint=URI_QUEUE_TRANSPORT)
            # 2. Allocate endpoint
            mediator_services = [service for service in mediator_did_doc['service'] if service['type'] == settings.MEDIATOR_SERVICE_TYPE]
            for service in mediator_services:
                assert 'endpoint' in service['serviceEndpoint']
                assert 'group_id' in service['serviceEndpoint']
                assert group_id in service['serviceEndpoint']
        finally:
            websocket.close()


def test_load_balancing_with_group_id(test_database: Database, random_me: (str, str, str), random_endpoint_uid: str):
    content_json = {'key1': 'value', 'key2': 123}
    content = json.dumps(content_json).encode()
    content_type = 'application/json'

    agent_did, agent_verkey, agent_secret = random_me
    redis_pub_sub = 'redis://redis1/%s' % uuid.uuid4().hex

    asyncio.get_event_loop().run_until_complete(ensure_endpoint_exists(
        db=test_database, uid=random_endpoint_uid, redis_pub_sub=redis_pub_sub,
        agent_id=agent_did, verkey=agent_verkey
    ))
    with client.websocket_connect(f"/{WS_PATH_PREFIX}?endpoint={random_endpoint_uid}&group_id=group1") as websocket1:
        with client.websocket_connect(f"/{WS_PATH_PREFIX}?endpoint={random_endpoint_uid}&group_id=group2") as websocket2:
            sleep(3)  # give websocket timeout to accept connection
            response = client.post(
                build_endpoint_url(random_endpoint_uid),
                headers={"Content-Type": content_type},
                data=content,
            )
            assert response.status_code == 202

            enc_msg = websocket1.receive_json()
            assert enc_msg == content_json
            enc_msg = websocket2.receive_json()
            assert enc_msg == content_json
