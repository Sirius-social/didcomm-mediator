import uuid
import hashlib

import pytest
from databases import Database

from app.core.storages import DatabaseKeyValueStorage


@pytest.mark.asyncio
async def test_database_kv_storage(test_database: Database):
    kv = DatabaseKeyValueStorage(engine=test_database)
    await kv.select_db('db1')

    await kv.set('key1', 'value1')
    value = await kv.get('key1')
    assert value == 'value1'

    await kv.select_db('db2')
    await kv.set('key1', 1000)
    value = await kv.get('key1')
    assert value == 1000

    await kv.select_db('db1')
    value = await kv.get('key1')
    assert value == 'value1'

    await kv.delete('key1')
    value = await kv.get('key1')
    assert value is None

    await kv.delete('unknown-key')


@pytest.mark.asyncio
async def test_inmemory_kv_storage_iteration(test_database: Database):
    kv = DatabaseKeyValueStorage(test_database)
    await kv.select_db('db1')
    data_under_test = {'key1': 'value1', 'key2': 12345}

    for k, v in data_under_test.items():
        await kv.set(k, v)

    loaded_data = await kv.items()
    assert loaded_data == data_under_test
