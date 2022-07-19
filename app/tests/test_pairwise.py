import pytest
from databases import Database
from sirius_sdk import Pairwise

from app.core.pairwise import MediatorPairwiseList, MediatorDID

from rfc.bus import *


@pytest.mark.asyncio
async def test_sane(test_database: Database, random_me: (str, str, str), random_their: (str, str, str)):
    my_did, my_verkey, _ = random_me
    their_did, their_verkey, _ = random_their
    p = Pairwise(
        me=Pairwise.Me(
            did=my_did, verkey=my_verkey
        ),
        their=Pairwise.Their(
            did=their_did, label='Test-Pairwise', endpoint='http://endpoint', verkey=their_verkey
        ),
        metadata=dict(test='test-value')
    )

    obj_under_test = MediatorPairwiseList(test_database)

    lst1 = []
    async for i in obj_under_test.enumerate():
        lst1.append(i)
    await obj_under_test.ensure_exists(p)
    lst2 = []
    async for i in obj_under_test.enumerate():
        lst2.append(i)
    assert len(lst1) < len(lst2)

    ok = await obj_under_test.is_exists(their_did)
    assert ok is True

    loaded = await obj_under_test.load_for_verkey(their_verkey)
    assert loaded.metadata == p.metadata
