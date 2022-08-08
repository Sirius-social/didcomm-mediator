import pytest

from rfc.pickup import *


@pytest.mark.asyncio
async def test_status_request():
    state_machine = PickUpStateMachine()
    msg_count = 10
    messages = []
    for n in range(msg_count):
        msg = {'@id': uuid.uuid4().hex, 'content': 'Content'}
        messages.append(msg)
    for msg in messages:
        await state_machine.put(msg)

    request = PickUpStatusRequest()
    response = await state_machine.process(request)
    assert isinstance(response, PickUpStatusResponse)
    assert response.message_count == msg_count
    assert response.last_added_time is not None


@pytest.mark.asyncio
async def test_list_request():
    state_machine = PickUpStateMachine()
    msg_count = 10
    messages = []
    for n in range(msg_count):
        msg = {'@id': uuid.uuid4().hex, 'content': 'Content'}
        messages.append(msg)
    for msg in messages:
        await state_machine.put(msg)

    first = messages[0]
    second = messages[1]
    known_msg_ids = [first['@id'], second['@id']]
    unknown_msg_id = uuid.uuid4().hex

    request = PickUpListRequest(message_ids=known_msg_ids + [unknown_msg_id])
    response = await state_machine.process(request)
    assert isinstance(response, PickUpListResponse)
    assert len(response.messages) == 2
    assert all([item.msg_id in known_msg_ids for item in response.messages])
    assert all([item.msg_id not in unknown_msg_id for item in response.messages])
    assert all([item.msg_id == item.message.get('@id', None) for item in response.messages])


@pytest.mark.asyncio
async def test_batch_request():
    state_machine = PickUpStateMachine()
    msg_count = 5
    messages = []
    for n in range(msg_count):
        msg = {'@id': uuid.uuid4().hex, 'content': 'Content'}
        messages.append(msg)
    for msg in messages:
        await state_machine.put(msg)

    chunk1 = messages[:3]
    chunk2 = messages[3:]

    # Step-1
    request = PickUpBatchRequest(batch_size=len(chunk1))
    response = await state_machine.process(request)
    assert isinstance(response, PickUpBatchResponse)
    assert len(response.messages) == 3
    assert list([item.msg_id for item in response.messages]) == list([msg['@id'] for msg in chunk1])
    # Step-2
    request = PickUpBatchRequest(batch_size=len(chunk2))
    response = await state_machine.process(request)
    assert isinstance(response, PickUpBatchResponse)
    assert len(response.messages) == 2
    assert list([item.msg_id for item in response.messages]) == list([msg['@id'] for msg in chunk2])
    # Step-3
    request = PickUpBatchRequest(batch_size=1, delay_timeout=1)
    for n in range(2):
        stamp1 = datetime.datetime.now()
        response = await state_machine.process(request)
        stamp2 = datetime.datetime.now()
        assert isinstance(response, PickUpBatchResponse)
        assert len(response.messages) == 0
        stamp_delta = stamp2 - stamp1
        assert 0.9 < stamp_delta.total_seconds() <= 1.1


@pytest.mark.asyncio
async def test_noop():
    state_machine = PickUpStateMachine()
    msg_count = 2
    messages = []
    for n in range(msg_count):
        msg = {'@id': uuid.uuid4().hex, 'content': 'Content'}
        messages.append(msg)
    for msg in messages:
        await state_machine.put(msg)

    request = PickUpNoop()
    response1 = await state_machine.process(request)
    assert response1 == messages[0]
    response2 = await state_machine.process(request)
    assert response2 == messages[1]


@pytest.mark.asyncio
async def test_noop_cpu_utilize():
    state_machine = PickUpStateMachine(max_queue_size=1)
    msg_count = 20
    messages = []
    for n in range(msg_count):
        msg = {'@id': uuid.uuid4().hex, 'content': f'Content-{n}'}
        messages.append(msg)

    async def __put__():
        for m in messages:
            await state_machine.put(m)
            print('#')
            await asyncio.sleep(0.1)
            print('#')

    fut = asyncio.ensure_future(__put__())

    request = PickUpNoop(delay_timeout=1)
    await asyncio.sleep(1)

    for expected_msg in messages:
        response = await state_machine.process(request)
        assert response == expected_msg


@pytest.mark.asyncio
async def test_max_queue_size():
    state_machine = PickUpStateMachine(max_queue_size=1)
    msg_count = 2
    messages = []
    for n in range(msg_count):
        msg = {'@id': uuid.uuid4().hex, 'content': 'Content'}
        messages.append(msg)

    async def async_writer(delay=0):
        await asyncio.sleep(delay)
        for m in messages:
            await state_machine.put(m)

    fut = asyncio.ensure_future(async_writer(3))
    try:
        for expected_msg in messages:
            print('')
            rcv_msg = await state_machine.process(request=PickUpNoop(delay_timeout=3))
            assert expected_msg == rcv_msg
    finally:
        fut.cancel()

    rcv_msg = await state_machine.process(request=PickUpNoop(delay_timeout=1))
    assert isinstance(rcv_msg, PickUpProblemReport)
