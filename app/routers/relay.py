import json
import logging

import sirius_sdk
from fastapi import APIRouter, WebSocket, Request

from app.settings import RELAY_KEYPAIR
from app.core.websocket_listener import WebsocketListener


router = APIRouter(
    prefix="",
    tags=["relay"],
)


@router.websocket("/")
async def onboard(websocket: WebSocket):
    await websocket.accept()
    listener = WebsocketListener(ws=websocket, my_keys=RELAY_KEYPAIR)
    async for event in listener:
        if event is None:
            await websocket.close()
            return
        logging.debug('========= EVENT ============')
        logging.debug(json.dumps(event, indent=2, sort_keys=True))
        logging.debug('============================')
        if isinstance(event.message, sirius_sdk.aries_rfc.Ping):
            ping: sirius_sdk.aries_rfc.Ping = event.message
            if ping.response_requested:
                pong = sirius_sdk.aries_rfc.Pong(ping_id=ping.id)
                await listener.response(for_event=event, message=pong)
        elif isinstance(event.message, sirius_sdk.aries_rfc.Invitation):
            print('$')


@router.post('/')
async def endpoint(request: Request):
    pass


@router.post('/{{agent_id}}')
async def endpoint(request: Request, agent_id: str):
    pass
