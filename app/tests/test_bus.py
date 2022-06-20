import json
import uuid
import asyncio

import pytest

from app.settings import REDIS as REDIS_SERVERS
from core.bus import Bus
from rfc.coprotocols import *


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

    async def publisher(topic_: str, delay: float = 0.1):
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

    op_subscribe1 = BusSubscribeOperation(cast1)
    assert op_subscribe1.cast.thid == 'some-thread-id'
    assert op_subscribe1.cast.sender_vk is None and op_subscribe1.cast.recipient_vk is None

    op_subscribe2 = BusSubscribeOperation(cast2)
    assert op_subscribe2.cast.thid is None
    assert op_subscribe2.cast.sender_vk == 'VK2'
    assert op_subscribe2.cast.recipient_vk == 'VK1'
