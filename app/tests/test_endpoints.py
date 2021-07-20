import json
import uuid
import asyncio
from time import sleep

import pytest
from databases import Database
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.dependencies import get_db
from app.utils import build_endpoint_url
from app.db.crud import ensure_endpoint_exists, load_endpoint
from app.settings import WS_PATH_PREFIX, WEBROOT
from app.core.redis import AsyncRedisChannel

from .helpers import override_get_db


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
