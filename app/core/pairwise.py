from contextlib import asynccontextmanager
from typing import List, Optional, Dict

from sirius_sdk import Pairwise
from databases import Database
from sirius_sdk.agent.pairwise import AbstractPairwiseList

from app.db.models import pairwises
from .did import MediatorDID


class MediatorPairwiseList(AbstractPairwiseList):

    def __init__(self, db: Database):
        self._db: Database = db
        self._did = MediatorDID(db)
        self._cached_metadata: Dict[str, dict] = {}
        self._cached: Dict[str, Pairwise] = {}

    async def create(self, pairwise: Pairwise):
        async with self.get_db_connection_lazy() as db:
            await self._did.store_their_did(did=pairwise.their.did, verkey=pairwise.their.verkey)
            metadata = pairwise.metadata or {}
            metadata.update(self._build_metadata(pairwise))
            sql = pairwises.insert()
            values = {
                "their_did": pairwise.their.did,
                "their_verkey": pairwise.their.verkey,
                "my_did": pairwise.me.did,
                "my_verkey": pairwise.me.verkey,
                "metadata": metadata,
                'their_label': pairwise.their.label
            }
            await db.execute(query=sql, values=values)
            self._cached_metadata[pairwise.their.did] = metadata

    async def update(self, pairwise: Pairwise):
        metadata = pairwise.metadata or {}
        metadata.update(self._build_metadata(pairwise))
        metadata_cached = self._cached_metadata.get(pairwise.their.did, None)
        if metadata_cached == metadata:
            return
        if pairwise.their.verkey in self._cached:
            del self._cached[pairwise.their.did]
        async with self.get_db_connection_lazy() as db:
            sql = pairwises.update().where(pairwises.c.their_did == pairwise.their.did)
            values = {
                "their_verkey": pairwise.their.verkey,
                "my_did": pairwise.me.did,
                "my_verkey": pairwise.me.verkey,
                "metadata": metadata,
                'their_label': pairwise.their.label
            }
            await db.execute(query=sql, values=values)
            self._cached_metadata[pairwise.their.did] = metadata

    async def is_exists(self, their_did: str) -> bool:
        async with self.get_db_connection_lazy() as db:
            sql = pairwises.select().where(pairwises.c.their_did == their_did)
            row = await db.fetch_one(query=sql)
            return row is not None

    async def ensure_exists(self, pairwise: Pairwise):
        if await self.is_exists(their_did=pairwise.their.did):
            await self.update(pairwise)
        else:
            await self.create(pairwise)

    async def load_for_did(self, their_did: str) -> Optional[Pairwise]:
        async with self.get_db_connection_lazy() as db:
            sql = pairwises.select().where(pairwises.c.their_did == their_did)
            row = await db.fetch_one(query=sql)
            if row:
                metadata = row['metadata']
                pairwise = self._restore_pairwise(metadata)
                return pairwise
            else:
                return None

    async def load_for_verkey(self, their_verkey: str) -> Optional[Pairwise]:
        if their_verkey in self._cached:
            return self._cached[their_verkey]
        async with self.get_db_connection_lazy() as db:
            sql = pairwises.select().where(pairwises.c.their_verkey == their_verkey)
            row = await db.fetch_one(query=sql)
            if row:
                metadata = row['metadata']
                pairwise = self._restore_pairwise(metadata)
                return pairwise
            else:
                return None

    async def _start_loading(self):
        self.__is_loading = True

    async def _partial_load(self) -> (bool, List[Pairwise]):
        async with self.get_db_connection_lazy() as db:
            if self.__is_loading:
                sql = pairwises.select()
                rows = await db.fetch_all(query=sql)
                self.__is_loading = False
                return True, [self._restore_pairwise(row['metadata']) for row in rows]
            else:
                return False, []

    async def _stop_loading(self):
        self.__is_loading = False

    @staticmethod
    def _restore_pairwise(metadata: dict):
        pairwise = Pairwise(
            me=Pairwise.Me(
                did=metadata.get('me', {}).get('did', None),
                verkey=metadata.get('me', {}).get('verkey', None),
                did_doc=metadata.get('me', {}).get('did_doc', None)
            ),
            their=Pairwise.Their(
                did=metadata.get('their', {}).get('did', None),
                verkey=metadata.get('their', {}).get('verkey', None),
                label=metadata.get('their', {}).get('label', None),
                endpoint=metadata.get('their', {}).get('endpoint', {}).get('address', None),
                routing_keys=metadata.get('their', {}).get('endpoint', {}).get('routing_keys', None),
                did_doc=metadata.get('their', {}).get('did_doc', None)
            ),
            metadata=metadata
        )
        return pairwise

    @staticmethod
    def _build_metadata(pairwise: Pairwise) -> dict:
        metadata = {
            'me': {
                'did': pairwise.me.did,
                'verkey': pairwise.me.verkey,
                'did_doc': pairwise.me.did_doc
            },
            'their': {
                'did': pairwise.their.did,
                'verkey': pairwise.their.verkey,
                'label': pairwise.their.label,
                'endpoint': {
                    'address': pairwise.their.endpoint,
                    'routing_keys': pairwise.their.routing_keys
                },
                'did_doc': pairwise.their.did_doc
            }
        }
        return metadata

    @asynccontextmanager
    async def get_db_connection_lazy(self):
        if not self._db.is_connected:
            await self._db.connect()
        yield self._db
