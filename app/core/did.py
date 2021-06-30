from typing import Any, Optional, List

from sirius_sdk.agent.wallet.abstract.did import AbstractDID


class RelayDID(AbstractDID):

    async def create_and_store_my_did(self, did: str = None, seed: str = None, cid: bool = None) -> (str, str):
        raise NotImplemented

    async def store_their_did(self, did: str, verkey: str = None) -> None:
        pass

    async def set_did_metadata(self, did: str, metadata: dict = None) -> None:
        pass

    async def list_my_dids_with_meta(self) -> List[Any]:
        raise NotImplemented

    async def get_did_metadata(self, did) -> Optional[dict]:
        pass

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
        pass

    async def get_key_metadata(self, verkey: str) -> dict:
        pass

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