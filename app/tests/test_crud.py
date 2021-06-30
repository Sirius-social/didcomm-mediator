import pytest
from databases import Database

from app.db.crud import ensure_agent_exists, load_agent


@pytest.mark.asyncio
async def test_agent_ops(test_database: Database, random_me: (str, str, str)):
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
