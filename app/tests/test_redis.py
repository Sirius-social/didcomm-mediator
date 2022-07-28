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
async def test_load_balancing_redis_group():

    reads1 = list()
    reads2 = list()
    writes = list()

    async def reader1(address: str, infinite: bool = False, group: str = None):
        nonlocal reads1
        ch = AsyncRedisGroup(address, group_id=group)
        while True:
            ok, data = await ch.read(DEF_TIMEOUT)
            reads1.append(tuple([ok, data]))
            if not ok:
                return
            if not infinite:
                break

    async def reader2(address: str, infinite: bool = False, group: str = None):
        nonlocal reads2
        ch = AsyncRedisGroup(address, group_id=group)
        while True:
            ok, data = await ch.read(DEF_TIMEOUT)
            reads2.append(tuple([ok, data]))
            if not ok:
                return
            if not infinite:
                break

    async def writer(address: str, count: int = 100):
        nonlocal writes
        ch = AsyncRedisGroup(address)
        for n in range(count):
            res = await ch.write({'key': f'value{n}'})
            writes.append(res)
            await ch.close()

    writes_count = 100
    group_id = 'group-id-' + uuid.uuid4().hex
    address = 'redis://redis1/%s' % uuid.uuid4().hex
    fut1 = asyncio.ensure_future(reader1(address, True, group_id))
    fut2 = asyncio.ensure_future(reader2(address, True, group_id))
    await asyncio.sleep(1)
    await writer(address, writes_count)
    await asyncio.sleep(5)
    assert len(reads1) < writes_count
    assert len(reads2) < writes_count
    assert len(reads1) + len(reads2) == writes_count
    assert writes == [True] * writes_count
    for n in range(writes_count):
        msg = {'key': f'value{n}'}
        if msg in reads1:
            assert msg not in reads2
        elif msg in reads2:
            assert msg not in reads1


@pytest.mark.asyncio
async def test_timeouts_redis_group():
    address = 'redis://redis1/%s' % uuid.uuid4().hex
    group_id = 'group_id_' + uuid.uuid4().hex
    ch_under_test = AsyncRedisGroup(address, group_id=group_id)

    async def __write_delayed__(addr_, data_, delay_):
        ch = AsyncRedisGroup(addr_)
        await asyncio.sleep(delay_)
        print('@')
        await ch.write(data_)

    # check-1
    print('@')
    with pytest.raises(ReadWriteTimeoutError):
        await ch_under_test.read(timeout=3)
    # check-2
    delay = 3
    data = {'marker': uuid.uuid4().hex}
    asyncio.ensure_future(__write_delayed__(address, data, delay))
    stamp1 = datetime.datetime.now()
    ok, rcv = await ch_under_test.read(timeout=None)
    assert ok is True
    assert rcv == data
    stamp2 = datetime.datetime.now()
    await_delta = stamp2 - stamp1
    assert delay <= await_delta.total_seconds() < delay+0.1


@pytest.mark.asyncio
async def test_clean_redis_group_on_close():
    address = 'redis://redis1/%s' % uuid.uuid4().hex
    group_id = 'group_id_' + uuid.uuid4().hex
    ch_under_test = AsyncRedisGroup(address, group_id=group_id)

    async def __write_delayed__(addr_, data_):
        await asyncio.sleep(1)
        ch = AsyncRedisGroup(addr_)
        print('@')
        await ch.write(data_)

    # Activate async-reader task
    asyncio.ensure_future(__write_delayed__(address, {'marker': uuid.uuid4().hex}))
    ok, rcv = await ch_under_test.read(timeout=3)
    assert ok

    # Check meta-info
    ch_infos = AsyncRedisGroup(address, group_id=group_id)
    infos1 = await ch_infos.info_consumers()
    assert len(infos1) == 1
    assert infos1[0][b'name'] == ch_under_test.self_id.encode()

    # Close Channel-Under-Test and re-check again
    await ch_under_test.close()
    await asyncio.sleep(1)
    infos2 = await ch_infos.info_consumers()
    assert len(infos2) == 0


@pytest.mark.asyncio
async def test_clean_redis_group_infinite_timeout():
    address = 'redis://redis1/%s' % uuid.uuid4().hex
    group_id = 'group_id_' + uuid.uuid4().hex
    ch_under_test = AsyncRedisGroup(address, group_id=group_id)

    async def __write_delayed__(addr_, data_):
        await asyncio.sleep(1)
        ch = AsyncRedisGroup(addr_)
        print('@')
        await ch.write(data_)

    # Activate async-reader task
    asyncio.ensure_future(__write_delayed__(address, {'marker': uuid.uuid4().hex}))
    ok, rcv = await ch_under_test.read(timeout=None)
    assert ok

    # Check meta-info
    ch_infos = AsyncRedisGroup(address, group_id=group_id)
    infos1 = await ch_infos.info_consumers()
    assert len(infos1) == 1
    assert infos1[0][b'name'] == ch_under_test.self_id.encode()

    # Close Channel-Under-Test and re-check again
    await ch_under_test.close()
    await asyncio.sleep(1)
    infos2 = await ch_infos.info_consumers()
    assert len(infos2) == 0


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
