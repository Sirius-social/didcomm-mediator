from typing import Any, Optional, List

from sirius_sdk.agent.wallet.abstract.did import AbstractDID


class LocalDID(AbstractDID):

    """You may override this code block with Aries-Askar"""

    def __init__(self):
        self._storage = dict()

    async def create_and_store_my_did(self, did: str = None, seed: str = None, cid: bool = None) -> (str, str):
        raise NotImplemented

    async def store_their_did(self, did: str, verkey: str = None) -> None:
        descriptor = self._storage.get(did, {})
        descriptor['verkey'] = verkey
        self._storage[did] = descriptor

    async def set_did_metadata(self, did: str, metadata: dict = None) -> None:
        descriptor = self._storage.get(did, {})
        descriptor['metadata'] = metadata
        self._storage[did] = descriptor

    async def list_my_dids_with_meta(self) -> List[Any]:
        raise NotImplemented

    async def get_did_metadata(self, did) -> Optional[dict]:
        descriptor = self._storage.get(did, {})
        return descriptor.get('metadata', None)

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
