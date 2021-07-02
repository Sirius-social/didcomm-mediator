import json
import logging

import sirius_sdk
from databases import Database
from fastapi import APIRouter, WebSocket, Request, Depends

from app.settings import RELAY_KEYPAIR, RELAY_DID, RELAY_LABEL
from app.core.coprotocols import ClientWebSocketCoProtocol
from app.core.websocket_listener import WebsocketListener
from app.db.crud import ensure_agent_exists
from app.dependencies import get_db


router = APIRouter(
    prefix="",
    tags=["mediator"],
)


@router.websocket("/")
async def onboard(websocket: WebSocket, db: Database = Depends(get_db)):
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
            inv: sirius_sdk.aries_rfc.Invitation = event.message
            their_vk = inv.recipient_keys[0]
            state_machine = sirius_sdk.aries_rfc.Invitee(
                me=sirius_sdk.Pairwise.Me(did=RELAY_DID, verkey=RELAY_KEYPAIR[0]),
                my_endpoint=sirius_sdk.Endpoint(address='ws://', routing_keys=[]),
                coprotocol=ClientWebSocketCoProtocol(
                    ws=websocket, my_keys=RELAY_KEYPAIR, their_verkey=their_vk
                )
            )
            try:
                success, p2p = await state_machine.create_connection(invitation=inv, my_label=RELAY_LABEL)
                if success:
                    await sirius_sdk.PairwiseList.ensure_exists(p2p)
                    await ensure_agent_exists(db, did=p2p.their.did, verkey=p2p.their.verkey, metadata=p2p.metadata)
            except Exception as e:
                raise


@router.post('/')
async def endpoint(request: Request):
    pass


@router.post('/{{agent_id}}')
async def endpoint(request: Request, agent_id: str):
    pass
