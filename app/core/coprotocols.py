import json
from typing import Tuple, Optional

from sirius_sdk import AbstractP2PCoProtocol
from sirius_sdk.encryption.ed25519 import pack_message, unpack_message
from sirius_sdk.messaging import Message
from starlette.websockets import WebSocket as FastAPIWebSocket


class ClientWebSocketCoProtocol(AbstractP2PCoProtocol):

    def __init__(self, ws: FastAPIWebSocket, my_keys: Tuple[str, str], their_verkey: str, time_to_live: int = None):
        super().__init__(time_to_live)
        self.__transport: FastAPIWebSocket = ws
        self.__my_keys = my_keys
        self.__their_verkey = their_verkey

    async def send(self, message: Message):
        payload = pack_message(
            message=json.dumps(message),
            to_verkeys=[self.__their_verkey],
            from_verkey=self.__my_keys[0],
            from_sigkey=self.__my_keys[1]
        )
        await self.__transport.send_bytes(payload)

    async def get_one(self) -> (Optional[Message], str, Optional[str]):
        payload = await self.__transport.receive_bytes()
        message, sender_vk, recip_vk = unpack_message(
            enc_message=payload,
            my_verkey=self.__my_keys[0],
            my_sigkey=self.__my_keys[1]
        )
        message = json.loads(message)
        return Message(**message), sender_vk, recip_vk

    async def switch(self, message: Message) -> (bool, Message):
        await self.send(message)
        msg, _, _ = await self.get_one()
        return True, msg