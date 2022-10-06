import base64
import json
from typing import Any, Optional

import sirius_sdk
from sirius_sdk.abstract.api import APICrypto
from sirius_sdk.encryption import sign_message, verify_signed_message, pack_message, \
    unpack_message, b58_to_bytes, bytes_to_b58, create_keypair


class LocalCrypto(APICrypto):

    """Crypto module on device side, for example Indy-Wallet or HSM or smth else

      - you may override this code block with Aries-Askar
    """

    def __init__(self, verkey: str, secret: str):
        self.__keys = []
        vk = b58_to_bytes(verkey)
        sk = b58_to_bytes(secret)
        self.__keys.append([vk, sk])

    async def create_key(self, seed: str = None, crypto_type: str = None) -> str:
        if seed:
            seed = seed.encode()
        else:
            seed = None
        vk, sk = create_keypair(seed)
        self.__keys.append([vk, sk])
        return bytes_to_b58(vk)

    async def set_key_metadata(self, verkey: str, metadata: dict) -> None:
        raise NotImplemented

    async def get_key_metadata(self, verkey: str) -> Optional[dict]:
        raise NotImplemented

    async def crypto_sign(self, signer_vk: str, msg: bytes) -> bytes:
        vk, sk = self.__check_verkey(signer_vk)
        signature = sign_message(
            message=msg,
            secret=sk
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
        vk, sk = self.__check_verkey(sender_verkey)
        if isinstance(message, dict):
            message = json.dumps(message)
        elif isinstance(message, bytes):
            message = message.decode()
        packed = pack_message(
            message=message,
            to_verkeys=recipient_verkeys,
            from_verkey=vk,
            from_sigkey=sk
        )
        return packed

    async def unpack_message(self, jwe: bytes):
        jwe = json.loads(jwe.decode())
        protected = jwe['protected']
        payload = json.loads(base64.b64decode(protected))
        recipients = payload['recipients']
        vk, sk = None, None
        for item in recipients:
            rcp_vk = b58_to_bytes(item['header']['kid'])
            for vk_, sk_ in self.__keys:
                if rcp_vk == vk_:
                    vk, sk = vk_, sk_
                    break
        if not vk:
            raise RuntimeError('Unknown recipient keys')
        message, sender_vk, recip_vk = unpack_message(
            enc_message=jwe,
            my_verkey=vk,
            my_sigkey=sk
        )
        message = json.loads(message)
        return message, sender_vk, recip_vk

    def __check_verkey(self, verkey: str) -> (bytes, bytes):
        verkey_bytes = b58_to_bytes(verkey)
        for vk, sk in self.__keys:
            if vk == verkey_bytes:
                return vk, sk
        raise RuntimeError('Unknown Verkey')


def create_did_and_keys(seed: str = None) -> (str, str, str):
    """
    :param seed: for const seed will be generated const did, verkey, secret
    :return: did, verkey, secret
    """

    if seed:
        seed = seed.encode()
    v, s = sirius_sdk.encryption.create_keypair(seed)
    verkey_ = sirius_sdk.encryption.bytes_to_b58(v)
    secret_ = sirius_sdk.encryption.bytes_to_b58(s)
    did_ = sirius_sdk.encryption.bytes_to_b58(sirius_sdk.encryption.did_from_verkey(v))
    return did_, verkey_, secret_
