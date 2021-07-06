import uuid
import asyncio

import pytest

from app.core.redis import *
from app.db.crud import ensure_endpoint_exists


DEF_TIMEOUT = 5


@pytest.mark.asyncio
async def test_sane():

    reads = list()
    writes = list()

    async def reader(address: str, infinite: bool = False):
        nonlocal reads
        ch = AsyncRedisChannel(address)
        while True:
            ok, data = await ch.read(DEF_TIMEOUT)
            reads.append(tuple([ok, data]))
            if not ok:
                return
            if not infinite:
                break

    async def writer(address: str):
        nonlocal writes
        ch = AsyncRedisChannel(address)
        res = await ch.write({'key': 'value1'})
        writes.append(res)
        res = await ch.write({'key': 'value2'})
        writes.append(res)
        await ch.close()

    success = await AsyncRedisChannel.check_address('redis://redis1')
    assert success is True
    success = await AsyncRedisChannel.check_address('redis://redis?')
    assert success is False
    address = 'redis://redis1/%s' % uuid.uuid4().hex
    fut = asyncio.ensure_future(reader(address, True))
    await asyncio.sleep(1)
    await writer(address)
    await asyncio.sleep(3)
    assert reads == [(True, {'key': 'value1'}), (True, {'key': 'value2'}), (False, None)]
    assert writes == [True, True]


@pytest.mark.asyncio
async def test_errors():

    async def reader(address: str):
        ch = AsyncRedisChannel(address)
        while True:
            await ch.read(3)

    invalid_address = 'redis://redisx/%s' % uuid.uuid4().hex
    with pytest.raises(RedisConnectionError):
        await reader(invalid_address)

    valid_address = 'redis://redis1/%s' % uuid.uuid4().hex
    with pytest.raises(ReadWriteTimeoutError):
        await reader(valid_address)


@pytest.mark.asyncio
async def test_push(test_database: Database, ):

    forward_channel_addr = 'redis://redis1/%s' % uuid.uuid4().hex
    endpoint_id = uuid.uuid4().hex
    await ensure_endpoint_exists(test_database, uid=endpoint_id, redis_pub_sub=forward_channel_addr)

    async def reader(address: str):
        try:
            print('#1')
            pull = RedisPull()
            print('#2')
            async for ok, request in pull.listen(address):
                print('===============')
                print(str(ok))
                print(str(request))
                await request.ack()
        except Exception as e:
            print('>>>>>>>>>>>>>>>>>>>>>')
            print(str(e))

    fut = asyncio.ensure_future(reader(forward_channel_addr))
    await asyncio.sleep(3)

    push = RedisPush(test_database)
    success = await push.push(
        endpoint_id=endpoint_id,
        message={
            'test': 'Hello'
        },
        ttl=15
    )
    fut.cancel()
    assert success is True
