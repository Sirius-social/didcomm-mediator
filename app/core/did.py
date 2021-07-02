from contextlib import asynccontextmanager
from typing import Any, Optional, List

from databases import Database
from sirius_sdk.agent.wallet.abstract.did import AbstractDID

from app.db.crud import ensure_agent_exists, load_agent


class MediatorDID(AbstractDID):

    def __init__(self, db: Database):
        self._db: Database = db

    async def create_and_store_my_did(self, did: str = None, seed: str = None, cid: bool = None) -> (str, str):
        raise NotImplemented

    async def store_their_did(self, did: str, verkey: str = None) -> None:
        async with self.get_db_connection_lazy() as db:
            await ensure_agent_exists(db, did, verkey)

    async def set_did_metadata(self, did: str, metadata: dict = None) -> None:
        async with self.get_db_connection_lazy() as db:
            async with db.transaction():
                agent = await load_agent(self._db, did)
                if agent:
                    verkey = agent['verkey']  # ensure verkey is same
                    await ensure_agent_exists(self._db, did, verkey, metadata)
                else:
                    raise RuntimeError(f'Unknown agent with did: {did}')

    async def list_my_dids_with_meta(self) -> List[Any]:
        raise NotImplemented

    async def get_did_metadata(self, did) -> Optional[dict]:
        async with self.get_db_connection_lazy() as db:
            agent = await load_agent(db, did)
            if agent:
                return agent['metadata']
            else:
                return None

    async def key_for_local_did(self, did: str) -> str:
        raise NotImplemented

    async def key_for_did(self, pool_name: str, did: str) -> str:
        raise NotImplemented

    async def create_key(self, seed: str = None) -> str:
        raise NotImplemented

    async def replace_keys_start(self, did: str, seed: str = None) -> str:
        raise NotImplemented

    async def replace_keys_apply(self, did: str) -> None:
        raise NotImplemented

    async def set_key_metadata(self, verkey: str, metadata: dict) -> None:
        raise NotImplemented

    async def get_key_metadata(self, verkey: str) -> dict:
        raise NotImplemented

    async def set_endpoint_for_did(self, did: str, address: str, transport_key: str) -> None:
        raise NotImplemented

    async def get_endpoint_for_did(self, pool_name: str, did: str) -> (str, Optional[str]):
        raise NotImplemented

    async def get_my_did_with_meta(self, did: str) -> Any:
        raise NotImplemented

    async def abbreviate_verkey(self, did: str, full_verkey: str) -> str:
        raise NotImplemented

    async def qualify_did(self, did: str, method: str) -> str:
        raise NotImplemented

    @asynccontextmanager
    async def get_db_connection_lazy(self):
        if not self._db.is_connected:
            await self._db.connect()
        yield self._db
