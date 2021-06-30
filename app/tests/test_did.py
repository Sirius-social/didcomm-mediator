import pytest
from databases import Database

from app.core.did import MediatorDID


@pytest.mark.asyncio
async def test_sane(test_database: Database, random_me: (str, str, str)):
    did, verkey, secret = random_me

    obj_under_test = MediatorDID(db=test_database)

    await obj_under_test.store_their_did(did, verkey)
    metadata = {'key1': 'value1', 'key2': 111}
    await obj_under_test.set_did_metadata(did, metadata)
    read_metadata = await obj_under_test.get_did_metadata(did)
    assert read_metadata == metadata

    read_metadata = await obj_under_test.get_did_metadata('invalid-did')
    assert read_metadata is None

    with pytest.raises(RuntimeError):
        await obj_under_test.set_did_metadata('invalid-did', metadata)
