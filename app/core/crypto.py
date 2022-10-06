import json
from typing import Any, Optional

from sirius_sdk.abstract.api import APICrypto
from sirius_sdk.encryption import sign_message, verify_signed_message, pack_message, \
    unpack_message, b58_to_bytes, bytes_to_b58


class MediatorCrypto(APICrypto):

    def __init__(self, verkey: str, secret: str):
        self.__verkey: bytes = b58_to_bytes(verkey)
        self.__secret: bytes = b58_to_bytes(secret)

    async def create_key(self, seed: str = None, crypto_type: str = None) -> str:
        raise NotImplemented

    async def set_key_metadata(self, verkey: str, metadata: dict) -> None:
        raise NotImplemented

    async def get_key_metadata(self, verkey: str) -> Optional[dict]:
        raise NotImplemented

    async def crypto_sign(self, signer_vk: str, msg: bytes) -> bytes:
        self.__check_verkey(signer_vk)
        signature = sign_message(
            message=msg,
            secret=self.__secret
        )
        return signature

    async def crypto_verify(self, signer_vk: str, msg: bytes, signature: bytes) -> bool:
        success = verify_signed_message(
            verkey=b58_to_bytes(signer_vk),
            msg=msg,
            signature=signature
        )
        return success

    async def anon_crypt(self, recipient_vk: str, msg: bytes) -> bytes:
        raise NotImplemented

    async def anon_decrypt(self, recipient_vk: str, encrypted_msg: bytes) -> bytes:
        raise NotImplemented

    async def pack_message(self, message: Any, recipient_verkeys: list, sender_verkey: str = None) -> bytes:
        self.__check_verkey(sender_verkey)
        if isinstance(message, dict):
            message = json.dumps(message)
        elif isinstance(message, bytes):
            message = message.decode()
        packed = pack_message(
            message=message,
            to_verkeys=recipient_verkeys,
            from_verkey=self.__verkey,
            from_sigkey=self.__secret
        )
        return packed

    async def unpack_message(self, jwe: bytes):
        message, sender_vk, recip_vk = unpack_message(
            enc_message=jwe,
            my_verkey=self.__verkey,
            my_sigkey=self.__secret
        )
        message = json.loads(message)
        return message, sender_vk, recip_vk

    def __check_verkey(self, verkey: str):
        if verkey != bytes_to_b58(self.__verkey):
            raise RuntimeError('Only single verkey supported')
