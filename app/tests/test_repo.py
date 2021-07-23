import uuid

import pytest
from databases import Database

from app.core.repo import Repo


@pytest.mark.asyncio
async def test_agent_ops(test_database: Database, random_me: (str, str, str), random_fcm_device_id: str):
    did, verkey, secret = random_me

    repo_under_test = Repo(db=test_database)

    await repo_under_test.ensure_agent_exists(did, verkey)
    # Check-1: ensure agent is stored in db
    agent = await repo_under_test.load_agent(did)
    assert agent is not None
    assert agent['id']
    assert agent['did'] == did
    assert agent['verkey'] == verkey
    assert agent['metadata'] is None
    # Check-2: check unknown agent is None
    agent = await repo_under_test.load_agent('invalid-did')
    assert agent is None
    # Check-3: update verkey
    verkey2 = 'VERKEY2'
    await repo_under_test.ensure_agent_exists(did, verkey2)
    agent = await repo_under_test.load_agent(did)
    assert agent['verkey'] == verkey2
    # Check-4: update metadata
    metadata = {'key1': 'value1', 'key2': 111}
    await repo_under_test.ensure_agent_exists(did, verkey2, metadata)
    agent = await repo_under_test.load_agent(did)
    assert agent['metadata'] == metadata
    # Check-5: call to ensure_exists don't clear metadata
    await repo_under_test.ensure_agent_exists(did, verkey2)
    agent = await repo_under_test.load_agent(did)
    assert agent['metadata'] == metadata
    # Check-6: FCM device id
    await repo_under_test.ensure_agent_exists(did, verkey=verkey2, fcm_device_id=random_fcm_device_id)
    agent = await repo_under_test.load_agent(did)
    assert agent['fcm_device_id'] == random_fcm_device_id
    # Check-7: load agent via verkey
    agent_via_verkey = await repo_under_test.load_agent_via_verkey(verkey2)
    assert agent == agent_via_verkey
    agent_via_verkey = await repo_under_test.load_agent_via_verkey(verkey2)
    assert agent == agent_via_verkey


@pytest.mark.asyncio
async def test_endpoints_ops(test_database: Database, random_redis_pub_sub: str, random_fcm_device_id: str):
    uid = uuid.uuid4().hex
    verkey = 'VERKEY'

    repo_under_test = Repo(db=test_database)

    await repo_under_test.ensure_endpoint_exists(uid, random_redis_pub_sub, verkey=verkey)
    # Check-1: ensure endpoint is stored in db
    endpoint = await repo_under_test.load_endpoint(uid)
    assert endpoint is not None
    assert endpoint['uid'] == uid
    assert endpoint['agent_id'] is None
    assert endpoint['redis_pub_sub'] == random_redis_pub_sub
    assert endpoint['verkey'] == verkey
    # Check-2: set agent_id
    agent_id = uuid.uuid4().hex
    await repo_under_test.ensure_endpoint_exists(uid, agent_id=agent_id)
    endpoint = await repo_under_test.load_endpoint(uid)
    assert endpoint is not None
    assert endpoint['uid'] == uid
    assert endpoint['agent_id'] == agent_id
    assert endpoint['redis_pub_sub'] == random_redis_pub_sub
    assert endpoint['verkey'] == verkey
    # Check-3: set verkey
    new_verkey = 'VERKEY2'
    await repo_under_test.ensure_endpoint_exists(uid, verkey=new_verkey)
    endpoint = await repo_under_test.load_endpoint(uid)
    assert endpoint is not None
    assert endpoint['uid'] == uid
    assert endpoint['agent_id'] == agent_id
    assert endpoint['redis_pub_sub'] == random_redis_pub_sub
    assert endpoint['verkey'] == new_verkey
    # Check-4: load via verkey
    endpoint = await repo_under_test.load_endpoint_via_verkey(new_verkey)
    assert endpoint is not None
    assert endpoint['uid'] == uid
    assert endpoint['verkey'] == new_verkey
    # Check-5: update fcm_device_id
    await repo_under_test.ensure_endpoint_exists(uid, fcm_device_id=random_fcm_device_id)
    endpoint = await repo_under_test.load_endpoint(uid)
    assert endpoint['fcm_device_id'] == random_fcm_device_id


@pytest.mark.asyncio
async def test_routing_keys_ops(test_database: Database, random_endpoint_uid: str):

    repo_under_test = Repo(db=test_database)

    # Check-1: add routing key
    key1 = f'{uuid.uuid4().hex}'
    added = await repo_under_test.add_routing_key(random_endpoint_uid, key1)
    assert added['endpoint_uid'] == random_endpoint_uid
    assert added['key'] == key1
    assert added['id']
    # Check-2: add routing key
    key2 = f'{uuid.uuid4().hex}'
    added = await repo_under_test.add_routing_key(random_endpoint_uid, key2)
    assert added['endpoint_uid'] == random_endpoint_uid
    assert added['key'] == key2
    assert added['id']
    # Check-3: list keys
    collection = await repo_under_test.list_routing_key(random_endpoint_uid)
    assert len(collection) == 2
    assert collection[0]['id'] == 1
    assert collection[0]['key'] == key1
    assert collection[1]['id'] == 2
    assert collection[1]['key'] == key2
    # Check-4: remove key
    await repo_under_test.remove_routing_key(random_endpoint_uid, key1)
    collection = await repo_under_test.list_routing_key(random_endpoint_uid)
    assert len(collection) == 1


@pytest.mark.asyncio
async def test_global_settings(test_database: Database):

    repo_under_test = Repo(db=test_database)
    param1 = f'param1-' + uuid.uuid4().hex
    param2 = f'param2-' + uuid.uuid4().hex

    value = await repo_under_test.get_global_setting(param1)
    assert value is None

    await repo_under_test.set_global_setting(param1, 'value-ver-1')
    for n in range(2):
        value = await repo_under_test.get_global_setting(param1)
        assert value == 'value-ver-1'
    await repo_under_test.set_global_setting(param1, 'value-ver-2')
    for n in range(2):
        value = await repo_under_test.get_global_setting(param1)
        assert value == 'value-ver-2'

    await repo_under_test.set_global_setting(param2, 1.1)
    for n in range(2):
        value = await repo_under_test.get_global_setting(param2)
        assert value == 1.1

    value = await repo_under_test.get_global_setting(param1)
    assert value == 'value-ver-2'
