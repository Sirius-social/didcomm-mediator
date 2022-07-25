import json
import uuid
import asyncio
from time import sleep

import pytest
from databases import Database
from fastapi.testclient import TestClient
from sirius_sdk.messaging import restore_message_instance

from app.main import app
from app.dependencies import get_db
from app.settings import REDIS as REDIS_SERVERS, WS_PATH_PREFIX
from core.bus import Bus
from app.utils import build_invitation
from app.routers.mediator_scenarios import URI_QUEUE_TRANSPORT, build_protocol_topic
from rfc.bus import *

from .helpers import override_get_db, override_sirius_sdk
from .emulators import DIDCommRecipient as ClientEmulator


client = TestClient(app)
client2 = TestClient(app)
app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
async def test_conn_pool_persist():
    bus = Bus()
    pools = set()
    for n in range(100):
        topic = f'topic-' + uuid.uuid4().hex
        pool = await bus.get_conn_pool(url=bus.get_topic_url(topic))
        pools.add(id(pool))
    assert len(pools) == len(REDIS_SERVERS)


@pytest.mark.asyncio
async def test_pub_sub():
    bus = Bus()
    topic = 'topic-' + uuid.uuid4().hex
    msg_to_send = [uuid.uuid4().hex.encode() for n in range(5)]
    rcv_messages = []

    async def publisher(delay: float = 0.1):
        await asyncio.sleep(delay)
        for msg in msg_to_send:
            count = await bus.publish(topic, msg)
            assert count == 1

    fut = asyncio.ensure_future(publisher())
    try:

        async for msg in bus.listen(topic):
            rcv_messages.append(msg)
            if len(rcv_messages) == 5:
                break

        assert rcv_messages == msg_to_send
    finally:
        fut.cancel()


@pytest.mark.asyncio
async def test_pub_sub_multiple_topics():
    topics = []
    urls = set()
    bus = Bus()
    rcv_messages = []
    for n in range(10):
        topic = f'topic-{n}-' + uuid.uuid4().hex
        topics.append(topic)
        url = bus.get_topic_url(topic)
        urls.add(url)

    assert len(urls) > 1

    async def publisher(topic_: str, delay: float = 0.5):
        await asyncio.sleep(delay)
        msg = json.dumps({'topic': topic_}).encode()
        count = await bus.publish(topic_, msg)
        assert count > 0, f'Recipient count: {count}'

    tasks = []
    for topic in topics:
        tsk = asyncio.create_task(publisher(topic))
        tasks.append(tsk)
    try:

        async def listener():
            async for msg in bus.listen(*topics):
                rcv_messages.append(msg)
                if len(rcv_messages) == len(topics):
                    break

        lst = asyncio.create_task(listener())
        tasks.append(lst)
        await asyncio.wait_for(lst, timeout=5)

        extracted_topics = [json.loads(msg.decode())['topic'] for msg in rcv_messages]
        assert set(extracted_topics) == set(topics)
    finally:
        print('===================')
        print(str(rcv_messages))
        for tsk in tasks:
            tsk.cancel()


@pytest.mark.asyncio
async def test_rfc_messages():
    cast1 = BusOperation.Cast(thid='some-thread-id')
    assert cast1.validate() is True
    cast2 = BusOperation.Cast(recipient_vk='VK1', sender_vk='VK2', protocols=['some-protocol'])
    assert cast2.validate() is True
    err_cast = BusOperation.Cast(recipient_vk='VK1', sender_vk='VK2')
    assert err_cast.validate() is False

    op_subscribe1 = BusSubscribeRequest(cast1)
    assert op_subscribe1.cast.thid == 'some-thread-id'
    assert op_subscribe1.cast.sender_vk is None and op_subscribe1.cast.recipient_vk is None

    op_subscribe2 = BusSubscribeRequest(cast2)
    assert op_subscribe2.cast.thid is None
    assert op_subscribe2.cast.sender_vk == 'VK2'
    assert op_subscribe2.cast.recipient_vk == 'VK1'

    bind = BusBindResponse(thread_id='some-bind-id')
    assert bind.thread_id == 'some-bind-id'

    ok, msg = restore_message_instance(
        {
            '@type': 'https://didcomm.org/bus/1.0/bind',
            '~thread': {'thid': 'some-binding-id2'}
        }
    )
    assert ok is True
    assert isinstance(msg, BusBindResponse)
    assert msg.thread_id == 'some-binding-id2'

    unsub = BusUnsubscribeRequest(thread_id='some-id')
    assert unsub.need_answer is None
    for flag in [True, False]:
        unsub.need_answer = flag
        assert unsub.need_answer is flag


def test_bus_rfc_raise_events_for_thid(test_database: Database, random_me: (str, str, str)):
    """Check typical Bus operations
    """
    content = b'Some-Message'

    override_sirius_sdk()

    agent_did, agent_verkey, agent_secret = random_me
    protocols_bus = Bus()

    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        try:
            sleep(3)  # give websocket timeout to accept connection
            cli = ClientEmulator(
                transport=websocket, mediator_invitation=build_invitation(),
                agent_did=agent_did, agent_verkey=agent_verkey, agent_secret=agent_secret
            )
            # 1. Establish connection with Mediator
            mediator_did_doc = cli.connect(endpoint=URI_QUEUE_TRANSPORT)
            # 2. Subscribe to thread
            sub_thid = 'some-thread-id-' + uuid.uuid4().hex
            bind = cli.subscribe(thid=sub_thid)
            assert isinstance(bind, BusBindResponse)
            assert bind.active is True
            assert isinstance(bind.thread_id, str) and len(bind.thread_id) > 0
            # 3. Publish payload to bus
            topic = build_protocol_topic(agent_did, bind.thread_id)
            recp_num = asyncio.get_event_loop().run_until_complete(protocols_bus.publish(topic, content))
            assert recp_num == 1
            # 4. Check delivery
            event = cli.pickup_batch(timeout=5)
            assert isinstance(event, BusEvent)
            assert event.payload == content
        finally:
            websocket.close()


def test_bus_rfc_raise_events_for_vk(test_database: Database, random_me: (str, str, str)):
    """Check typical Bus operations
    """
    content = b'Some-Message'

    override_sirius_sdk()

    agent_did, agent_verkey, agent_secret = random_me
    protocols_bus = Bus()

    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        try:
            sleep(3)  # give websocket timeout to accept connection
            cli = ClientEmulator(
                transport=websocket, mediator_invitation=build_invitation(),
                agent_did=agent_did, agent_verkey=agent_verkey, agent_secret=agent_secret
            )
            # 1. Establish connection with Mediator
            mediator_did_doc = cli.connect(endpoint=URI_QUEUE_TRANSPORT)
            # 2. Subscribe to VKs
            bind = cli.subscribe(sender_vk='VK1', recipient_vk=['VK2', 'VK3'], protocols=['proto1', 'proto2'])
            assert isinstance(bind, BusBindResponse)
            assert bind.active is True
            assert isinstance(bind.thread_id, str) and len(bind.thread_id) > 0
            # 3. Publish payload to bus
            topic = build_protocol_topic(agent_did, bind.thread_id)
            recp_num = asyncio.get_event_loop().run_until_complete(protocols_bus.publish(topic, content))
            assert recp_num == 1
            # 4. Check delivery
            event = cli.pickup_batch(timeout=5)
            assert isinstance(event, BusEvent)
            assert event.payload == content
        finally:
            websocket.close()


def test_bus_rfc_multiple_topics(test_database: Database, random_me: (str, str, str)):
    """Check typical Bus operations
    """
    content1 = b'Some-Message-1'
    content2 = b'Some-Message-2'

    override_sirius_sdk()

    agent_did, agent_verkey, agent_secret = random_me
    protocols_bus = Bus()
    thid1 = 'thread-1-' + uuid.uuid4().hex
    thid2 = 'thread-2-' + uuid.uuid4().hex
    thread_ids = {}

    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        try:
            sleep(3)  # give websocket timeout to accept connection
            cli = ClientEmulator(
                transport=websocket, mediator_invitation=build_invitation(),
                agent_did=agent_did, agent_verkey=agent_verkey, agent_secret=agent_secret
            )
            # 1. Establish connection with Mediator
            mediator_did_doc = cli.connect(endpoint=URI_QUEUE_TRANSPORT)
            # 2. Subscribe to Thread-1 & Thread-2
            for thid in [thid1, thid2]:
                bind = cli.subscribe(thid=thid)
                assert isinstance(bind, BusBindResponse)
                assert bind.active is True
                thread_ids[thid] = bind.thread_id
            # 3. Publish to Thread-1 & Thread-2
            for thid, content in [(thid1, content1), (thid2, content2)]:
                topic = build_protocol_topic(agent_did, thread_ids[thid])
                recp_num = asyncio.get_event_loop().run_until_complete(protocols_bus.publish(topic, content))
                assert recp_num == 1
            # 4. Read income events
            income_events = []
            for n in range(2):
                event = cli.pickup_batch(timeout=5)
                income_events.append(event.payload)
            assert content1 in income_events
            assert content2 in income_events
            # 5. Unsubscribe from Thread-2
            unbind = cli.unsubscribe(thread_id=thread_ids[thid2])
            assert isinstance(unbind, BusBindResponse)
            assert unbind.active is False
            assert unbind.thread_id == thread_ids[thid2]
            # 6. Publish again
            for thid, expected_recip_num in [(thid1, 1), (thid2, 0)]:
                topic = build_protocol_topic(agent_did, thread_ids[thid])
                recp_num = asyncio.get_event_loop().run_until_complete(protocols_bus.publish(topic, content))
                assert recp_num == expected_recip_num
        finally:
            websocket.close()


def test_bus_rfc_publish(test_database: Database, random_me: (str, str, str)):
    """Check publish Bus operations
        """
    content = b'Some-Message-X'

    override_sirius_sdk()

    agent_did, agent_verkey, agent_secret = random_me
    thid = 'thread-' + uuid.uuid4().hex
    received_messages = []

    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket1:
        with client2.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket2:
            try:
                sleep(3)  # give websocket timeout to accept connection
                cli1 = ClientEmulator(
                    transport=websocket1, mediator_invitation=build_invitation(),
                    agent_did=agent_did, agent_verkey=agent_verkey, agent_secret=agent_secret
                )
                cli2 = ClientEmulator(
                    transport=websocket1, mediator_invitation=build_invitation(),
                    agent_did=agent_did, agent_verkey=agent_verkey, agent_secret=agent_secret
                )
                # 1. Establish connection with Mediator
                cli1.connect(endpoint=URI_QUEUE_TRANSPORT)
                cli2.connect(endpoint=URI_QUEUE_TRANSPORT)
                cli2.subscribe(thid=thid)
                # 2. Publish to Thread
                resp = cli1.publish(thread_id=thid, payload=content)
                assert isinstance(resp, BusPublishResponse)
                assert resp.recipients_num > 0
                event = cli2.pickup_batch(timeout=5)
                assert isinstance(event, BusEvent)
                assert event.payload == content
                assert event.thread_id == thid
                assert event.parent_thread_id is not None
                print(json.dumps(event, sort_keys=True, indent=2))
            finally:
                websocket1.close()
                websocket2.close()


def test_bus_rfc_aborting(test_database: Database, random_me: (str, str, str)):
    """Check typical Bus operations
    """

    override_sirius_sdk()

    agent_did, agent_verkey, agent_secret = random_me
    protocols_bus = Bus()

    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        try:
            sleep(3)  # give websocket timeout to accept connection
            cli = ClientEmulator(
                transport=websocket, mediator_invitation=build_invitation(),
                agent_did=agent_did, agent_verkey=agent_verkey, agent_secret=agent_secret
            )
            # 1. Establish connection with Mediator
            mediator_did_doc = cli.connect(endpoint=URI_QUEUE_TRANSPORT)
            # 2. Subscribe to thread
            sub_thid = 'some-thread-id-' + uuid.uuid4().hex
            bind = cli.subscribe(thid=sub_thid)
            assert bind.parent_thread_id is not None
            cli.abort(wait_answer=False)
            unbind = cli.pickup_batch(5)
            assert unbind.aborted is True
            assert unbind.active is False
            assert unbind.parent_thread_id is not None
            
        finally:
            websocket.close()


def test_bus_listener_no_intersections_if_group_id_set(
        test_database: Database, random_me: (str, str, str), didcomm_envelope_enc_content: bytes
):
    """Check delivery with Queue-Route DIDComm extension will not intersect with streams of bus messages
    """

    override_sirius_sdk()

    agent_did, agent_verkey, agent_secret = random_me
    content_type = 'application/didcomm-envelope-enc'

    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        try:
            sleep(3)  # give websocket timeout to accept connection
            cli = ClientEmulator(
                transport=websocket, mediator_invitation=build_invitation(),
                agent_did=agent_did, agent_verkey=agent_verkey, agent_secret=agent_secret, group_id='Some-Group-ID'
            )
            # 1. Establish connection with Mediator VIA "didcomm:transport/queue" mechanism
            mediator_did_doc = cli.connect(endpoint=URI_QUEUE_TRANSPORT)
            # 2. Allocate endpoint
            mediate_grant = cli.mediate_grant()
            # 2. Subscribe to thread
            thid = 'some-thread-id-' + uuid.uuid4().hex
            cli.subscribe(thid=thid)

            # 3. Post wired via endpoint
            response = client.post(
                mediate_grant['endpoint'],
                headers={"Content-Type": content_type},
                data=didcomm_envelope_enc_content
            )
            # 4. No-one active recipient
            assert response.status_code == 202
        finally:
            websocket.close()


def test_bus_listener_no_intersections_if_group_id_notset(
        test_database: Database, random_me: (str, str, str), didcomm_envelope_enc_content: bytes
):
    """Check delivery with Queue-Route DIDComm extension will not intersect with streams of bus messages
    """

    override_sirius_sdk()

    agent_did, agent_verkey, agent_secret = random_me
    content_type = 'application/didcomm-envelope-enc'

    with client.websocket_connect(f"/{WS_PATH_PREFIX}") as websocket:
        try:
            sleep(3)  # give websocket timeout to accept connection
            cli = ClientEmulator(
                transport=websocket, mediator_invitation=build_invitation(),
                agent_did=agent_did, agent_verkey=agent_verkey, agent_secret=agent_secret
            )
            # 1. Establish connection with Mediator VIA "didcomm:transport/queue" mechanism
            mediator_did_doc = cli.connect(endpoint=URI_QUEUE_TRANSPORT)
            # 2. Allocate endpoint
            mediate_grant = cli.mediate_grant()
            # 2. Subscribe to thread
            thid = 'some-thread-id-' + uuid.uuid4().hex
            cli.subscribe(thid=thid)

            # 3. Post wired via endpoint
            response = client.post(
                mediate_grant['endpoint'],
                headers={"Content-Type": content_type},
                data=didcomm_envelope_enc_content
            )
            # 4. No-one active recipient
            assert response.status_code == 410
        finally:
            websocket.close()
