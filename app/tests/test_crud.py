import uuid

import pytest
from databases import Database

from app.db.crud import *


@pytest.mark.asyncio
async def test_agent_ops(test_database: Database, random_me: (str, str, str), random_fcm_device_id: str):
    did, verkey, secret = random_me
    await ensure_agent_exists(test_database, did, verkey)
    # Check-1: ensure agent is stored in db
    agent = await load_agent(test_database, did)
    assert agent is not None
    assert agent['id']
    assert agent['did'] == did
    assert agent['verkey'] == verkey
    assert agent['metadata'] is None
    # Check-2: check unknown agent is None
    agent = await load_agent(test_database, 'invalid-did')
    assert agent is None
    # Check-3: update verkey
    verkey2 = 'VERKEY2'
    await ensure_agent_exists(test_database, did, verkey2)
    agent = await load_agent(test_database, did)
    assert agent['verkey'] == verkey2
    # Check-4: update metadata
    metadata = {'key1': 'value1', 'key2': 111}
    await ensure_agent_exists(test_database, did, verkey2, metadata)
    agent = await load_agent(test_database, did)
    assert agent['metadata'] == metadata
    # Check-5: call to ensure_exists don't clear metadata
    await ensure_agent_exists(test_database, did, verkey2)
    agent = await load_agent(test_database, did)
    assert agent['metadata'] == metadata
    # Check-6: FCM device id
    await ensure_agent_exists(test_database, did, verkey=verkey2, fcm_device_id=random_fcm_device_id)
    agent = await load_agent(test_database, did)
    assert agent['fcm_device_id'] == random_fcm_device_id
    # Check-7: load agent via verkey
    agent_via_verkey = await load_agent_via_verkey(test_database, verkey2)
    assert agent == agent_via_verkey


@pytest.mark.asyncio
async def test_endpoints_ops(test_database: Database, random_redis_pub_sub: str, random_fcm_device_id: str):
    uid = uuid.uuid4().hex
    verkey = 'VERKEY'
    await ensure_endpoint_exists(test_database, uid, random_redis_pub_sub, verkey=verkey)
    # Check-1: ensure endpoint is stored in db
    endpoint = await load_endpoint(test_database, uid)
    assert endpoint is not None
    assert endpoint['uid'] == uid
    assert endpoint['agent_id'] is None
    assert endpoint['redis_pub_sub'] == random_redis_pub_sub
    assert endpoint['verkey'] == verkey
    assert endpoint['fcm_device_id'] is None
    # Check-2: set agent_id
    agent_id = uuid.uuid4().hex
    await ensure_endpoint_exists(test_database, uid, agent_id=agent_id)
    endpoint = await load_endpoint(test_database, uid)
    assert endpoint is not None
    assert endpoint['uid'] == uid
    assert endpoint['agent_id'] == agent_id
    assert endpoint['redis_pub_sub'] == random_redis_pub_sub
    assert endpoint['verkey'] == verkey
    # Check-3: set verkey
    new_verkey = 'VERKEY2'
    await ensure_endpoint_exists(test_database, uid, verkey=new_verkey)
    endpoint = await load_endpoint(test_database, uid)
    assert endpoint is not None
    assert endpoint['uid'] == uid
    assert endpoint['agent_id'] == agent_id
    assert endpoint['redis_pub_sub'] == random_redis_pub_sub
    assert endpoint['verkey'] == new_verkey
    # Check-4: load via verkey
    endpoint = await load_endpoint_via_verkey(test_database, new_verkey)
    assert endpoint is not None
    assert endpoint['uid'] == uid
    assert endpoint['verkey'] == new_verkey
    # Check-5: update fcm_device_id
    await ensure_endpoint_exists(test_database, uid, fcm_device_id=random_fcm_device_id)
    endpoint = await load_endpoint(test_database, uid)
    assert endpoint['fcm_device_id'] == random_fcm_device_id


@pytest.mark.asyncio
async def test_routing_keys_ops(test_database: Database, random_endpoint_uid: str):
    # Check-1: add routing key
    key1 = f'{uuid.uuid4().hex}'
    added = await add_routing_key(test_database, random_endpoint_uid, key1)
    assert added['endpoint_uid'] == random_endpoint_uid
    assert added['key'] == key1
    assert added['id']
    # Check-2: add routing key
    key2 = f'{uuid.uuid4().hex}'
    added = await add_routing_key(test_database, random_endpoint_uid, key2)
    assert added['endpoint_uid'] == random_endpoint_uid
    assert added['key'] == key2
    assert added['id']
    # Check-3: list keys
    collection = await list_routing_key(test_database, random_endpoint_uid)
    assert len(collection) == 2
    assert collection[0]['id'] == 1
    assert collection[0]['key'] == key1
    assert collection[1]['id'] == 2
    assert collection[1]['key'] == key2
    # Check-4: remove key
    await remove_routing_key(test_database, random_endpoint_uid, key1)
    collection = await list_routing_key(test_database, random_endpoint_uid)
    assert len(collection) == 1


@pytest.mark.asyncio
async def test_agents_duplicates_for_verkey(test_database: Database, random_me: (str, str, str), random_their: (str, str, str)):
    """Check there no two ore more agents with same verkey
    """
    did1, verkey, _ = random_me
    await ensure_agent_exists(test_database, did1, verkey)
    did2, _, _ = random_their
    await ensure_agent_exists(test_database, did2, verkey)
    # ensure verkey was replaced
    sql = agents.select().where(agents.c.verkey == verkey)
    rows = await test_database.fetch_all(query=sql)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_endpoints_duplicates_for_verkey(test_database: Database, random_me: (str, str, str)):
    """Check there no two ore more endpoints with same verkey
    """
    _, verkey, _ = random_me
    uid1 = uuid.uuid4().hex
    uid2 = uuid.uuid4().hex
    await ensure_endpoint_exists(test_database, uid=uid1, verkey=verkey)
    await ensure_endpoint_exists(test_database, uid=uid2, verkey=verkey)
    # ensure verkey was replaced
    sql = endpoints.select().where(endpoints.c.verkey == verkey)
    rows = await test_database.fetch_all(query=sql)
    assert len(rows) == 1
