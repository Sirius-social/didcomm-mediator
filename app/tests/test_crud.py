import uuid
import hashlib

import pytest
from databases import Database

from app.db.crud import *
from app.db.models import pairwises


@pytest.mark.asyncio
async def test_user_ops(test_database: Database, random_username: str, random_password: str):
    # create user
    created_user = await create_user(test_database, random_username, random_password)
    assert created_user['username'] == random_username
    assert created_user['hashed_password'] != random_password, 'Password mangling error - security issue'
    assert created_user['is_active'] is True
    # Check password
    assert check_password(created_user, random_password) is True
    assert check_password(created_user, 'invalid-password') is False
    # Load user
    loaded_user = await load_user(test_database, random_username)
    assert loaded_user == created_user
    # Check exceptions
    with pytest.raises(DuplicateDBRecordError):
        await create_user(test_database, random_username, random_password)
    with pytest.raises(DBRecordDoesNotExists):
        await load_user(test_database, 'unknown-username')
    # Check clear accounts
    await reset_accounts(test_database)
    with pytest.raises(DBRecordDoesNotExists):
        await load_user(test_database, random_username)


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
    # Check-3: load endpoint via routing_key
    endpoint1 = await load_endpoint_via_routing_key(test_database, key1)
    endpoint2 = await load_endpoint_via_routing_key(test_database, key2)
    assert endpoint1 and endpoint2 and (endpoint1 == endpoint2)
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


@pytest.mark.asyncio
async def test_global_settings(test_database: Database):
    """Check Global settings for database operations pass expectations
    """
    value = await get_global_setting(test_database, 'param1')
    assert value is None

    await set_global_setting(test_database, 'param1', 'value-ver-1')
    value = await get_global_setting(test_database, 'param1')
    assert value == 'value-ver-1'

    await set_global_setting(test_database, 'param2', 1.1)
    value = await get_global_setting(test_database, 'param2')
    assert value == 1.1

    value = await get_global_setting(test_database, 'param1')
    assert value == 'value-ver-1'

    await reset_global_settings(test_database)
    for param in ['param1', 'param2']:
        value = await get_global_setting(test_database, param)
        assert value is None


@pytest.mark.asyncio
async def test_backups(test_database: Database):
    """Check backups CRUD operations
    """
    # 1. check load for empty value
    ok, dump, ctx = await load_backup(test_database, 'category')
    assert ok is False
    assert dump is None
    assert ctx is None
    # 2. save backup
    ctx = {
        'email': 'x@gmail.com',
        'share': True,
        'adv': 'something-else'
    }
    dump = b'big-data'
    await dump_backup(test_database, 'category', binary=dump, context=ctx)
    ok, loaded_dump, loaded_ctx = await load_backup(test_database, 'category')
    assert ok is True
    assert loaded_dump == dump
    assert loaded_ctx == ctx
    # 3. save updated dump
    new_dump = b'new-big-data'
    await dump_backup(test_database, 'category', binary=new_dump, context=ctx)
    ok, loaded_dump, loaded_ctx = await load_backup(test_database, 'category')
    assert ok is True
    assert loaded_dump == new_dump
    assert loaded_ctx == ctx
    # 4. dump file
    path = '/usr/bin/unzip'
    await dump_path(test_database, 'file', path, {})
    base_dir = '/tmp'
    ok, restored_path, ctx = await restore_path(test_database, 'file', base_dir=base_dir)
    assert ok is True
    assert path in restored_path
    with open(path, "rb") as f:
        file_hash_orig = hashlib.md5()
        file_hash_orig.update(f.read())
    with open(restored_path, "rb") as f:
        file_hash_restored = hashlib.md5()
        file_hash_restored.update(f.read())
    assert file_hash_orig.hexdigest() == file_hash_restored.hexdigest()
    # if restored file already exists
    ok, restored_path, ctx = await restore_path(test_database, 'file', base_dir=base_dir)
    assert ok is True
    # 3.1 check symlink
    path = '/usr/bin/unzip'
    link = '/tmp/unzip.link'
    exit_code = os.system(f'ln -s {path} {link}')
    assert exit_code == 0
    await dump_path(test_database, 'link', link, {})
    base_dir = '/tmp'
    ok, restored_path, ctx = await restore_path(test_database, 'link', base_dir=base_dir)
    assert ok is True
    assert link in restored_path
    with open(path, "rb") as f:
        file_hash_orig = hashlib.md5()
        file_hash_orig.update(f.read())
    with open(restored_path, "rb") as f:
        file_hash_restored = hashlib.md5()
        file_hash_restored.update(f.read())
    assert file_hash_orig.hexdigest() == file_hash_restored.hexdigest()
    # 4. dump dir
    path = '/etc/letsencrypt'
    await dump_path(test_database, 'dir', path, {})
    base_dir = '/tmp'
    ok, restored_path, ctx = await restore_path(test_database, 'dir', base_dir=base_dir)
    assert ok is True
    assert path in restored_path
    dir_hash_orig = hashlib.md5()
    dir_hash_restored = hashlib.md5()
    for root, dir, files in os.walk(path):
        for file in files:
            with open(os.path.join(root, file), "rb") as f:
                dir_hash_orig.update(f.read())
    for root, dir, files in os.walk(restored_path):
        for file in files:
            with open(os.path.join(root, file), "rb") as f:
                dir_hash_restored.update(f.read())
    assert file_hash_orig.hexdigest() == file_hash_restored.hexdigest()
    # if restored dir already exists
    ok, restored_path, ctx = await restore_path(test_database, 'dir', base_dir=base_dir)
    assert ok is True


@pytest.mark.asyncio
async def test_load_pairwise_collection(test_database: Database, random_me: (str, str, str)):
    pairwise_count = 100

    for n in range(pairwise_count):
        p2p = {
            'their_did': f'their_did{n}',
            'their_verkey': f'their_verkey{n}',
            'my_did': f'my_did{n}',
            'my_verkey': f'my_verkey{n}',
            'metadata': {},
            'their_label': f'label{n}'
        }
        sql = pairwises.insert()
        await test_database.execute(query=sql, values=p2p)

    # test Sane
    collection = await load_pairwises(test_database)
    assert len(collection) == pairwise_count
    for n in range(pairwise_count):
        e = collection[n]
        assert e['their_did'] == f'their_did{n}'
    # test pagination
    collection = await load_pairwises(test_database, offset=90)
    assert len(collection) == 10
    collection = await load_pairwises(test_database, limit=10)
    assert len(collection) == 10
    collection = await load_pairwises(test_database, limit=10, offset=10)
    assert len(collection) == 10
    assert collection[0]['their_did'] == 'their_did10'
    assert collection[-1]['their_did'] == 'their_did19'
    # test filters
    collection = await load_pairwises(test_database, filters={'their_did': 'their_did10'})
    assert len(collection) == 1
    assert collection[0]['their_did'] == 'their_did10'
    collection = await load_pairwises(test_database, filters={'their_label': 'label1'})
    assert len(collection) == 11
    assert collection[0]['their_label'] == 'label1'
    assert collection[1]['their_label'] == 'label10'
    assert collection[-1]['their_label'] == 'label19'
    collection = await load_pairwises(test_database, filters={'their_did': 'their_did10', 'their_label': 'label11'})
    assert len(collection) == 2
    assert collection[0]['their_did'] == 'their_did10'
    assert collection[1]['their_label'] == 'label11'
    # test count
    cnt = await load_pairwises_count(test_database)
    assert cnt == pairwise_count
    cnt = await load_pairwises_count(test_database, filters={'their_did': 'their_did10', 'their_label': 'label11'})
    assert cnt == 2
    cnt = await load_pairwises_count(test_database, filters={'their_label': 'label1'})
    assert cnt == 11
