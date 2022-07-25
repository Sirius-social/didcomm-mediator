import json
import uuid
import asyncio
from typing import Tuple, Optional

import sirius_sdk
from fastapi import WebSocket, WebSocketDisconnect
from sirius_sdk.agent.listener import Event
from sirius_sdk.messaging import restore_message_instance, Message
from sirius_sdk.encryption import unpack_message, pack_message

from rfc.decorators import *


class WebsocketListener:

    def __init__(self, ws: WebSocket, my_keys: Tuple[str, str]):
        self.__ws: WebSocket = ws
        self.__my_keys = my_keys

    async def response(self, for_event: Event, message: dict):
        if for_event.message is not None:
            income_msg: Message = for_event.message
            if get_thread_id(message) is None:
                income_return_route = get_return_route(income_msg)
                income_thread_id = get_thread_id(income_msg) or get_ack_message_id(income_msg)
                if income_thread_id:
                    set_thread_id(message, income_thread_id)
                elif income_return_route == 'thread':
                    set_thread_id(message, income_msg.id)
        if for_event.sender_verkey:
            packed = pack_message(
                message=json.dumps(message),
                to_verkeys=[for_event.sender_verkey],
                from_verkey=self.__my_keys[0],
                from_sigkey=self.__my_keys[1]
            )
            await self.__ws.send_bytes(packed)
        else:
            payload = json.dumps(message).encode()
            await self.__ws.send_bytes(payload)

    async def get_one(self) -> Event:
        b = await self.__ws.receive_bytes()
        payload = json.loads(b)
        event = {
            '@type': 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/sirius_rpc/1.0/event',
            '@id': uuid.uuid4().hex,
        }
        p2p: Optional[sirius_sdk.Pairwise] = None
        if 'protected' in payload:
            s, sender_vk, recip_vk = unpack_message(
                enc_message=payload,
                my_verkey=self.__my_keys[0],
                my_sigkey=self.__my_keys[1]
            )
            payload = json.loads(s)
            success, msg = restore_message_instance(payload)
            if success:
                event['message'] = msg
            else:
                event['message'] = Message(**payload)
            event['recipient_verkey'] = recip_vk
            event['sender_verkey'] = sender_vk
            p2p = await sirius_sdk.PairwiseList.load_for_verkey(sender_vk)
        else:
            success, msg = restore_message_instance(payload)
            if success:
                event['message'] = msg
            else:
                event['message'] = Message(**payload)
        return Event(pairwise=p2p, **event)

    def __aiter__(self):
        return self

    @asyncio.coroutine
    def __anext__(self):
        while True:
            try:
                return (yield from self.get_one())
            except WebSocketDisconnect:
                return None
