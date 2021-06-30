import pytest
from databases import Database

from app.core.did import RelayDID


@pytest.mark.asyncio
async def test_sane(test_database: Database):
    did = RelayDID(db=test_database)
    await did.store_their_did('did', 'verkey')
