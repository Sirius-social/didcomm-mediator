import json
import logging
import hashlib
from urllib.parse import urljoin

import sirius_sdk
from databases import Database
from fastapi import APIRouter, WebSocket, Request, Depends
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol.messages import ConnProtocolMessage
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import *

from app.settings import KEYPAIR, DID, MEDIATOR_LABEL, FCM_SERVICE_TYPE, MEDIATOR_SERVICE_TYPE, WEBROOT, REDIS
from app.core.coprotocols import ClientWebSocketCoProtocol
from app.core.redis import choice_server_address as choice_redis_server_address
from app.core.websocket_listener import WebsocketListener
from app.db.crud import ensure_agent_exists, load_endpoint_via_verkey, ensure_endpoint_exists, load_agent
from app.dependencies import get_db


router = APIRouter(
    prefix="",
    tags=["mediator"],
)


WS_ENDPOINT = 'ws://'


@router.websocket("/")
async def onboard(websocket: WebSocket, db: Database = Depends(get_db)):
    await websocket.accept()

    # Wrap parsing and unpacking enc_messages in listener
    listener = WebsocketListener(ws=websocket, my_keys=KEYPAIR)
    async for event in listener:

        if event is None:  # Stop listening: websocket die
            await websocket.close()
            return
        logging.debug('========= EVENT ============')
        logging.debug(json.dumps(event, indent=2, sort_keys=True))
        logging.debug('============================')

        # TODO: raise error and problem_report if not packed (avoiding 0160 protocol)
        if isinstance(event.message, sirius_sdk.aries_rfc.Ping):
            # Agent sent Ping to check connection
            ping: sirius_sdk.aries_rfc.Ping = event.message
            if ping.response_requested:
                pong = sirius_sdk.aries_rfc.Pong(ping_id=ping.id)
                await listener.response(for_event=event, message=pong)
        elif isinstance(event.message, sirius_sdk.aries_rfc.Invitation):
            # Agent was start p2p establish
            inv: sirius_sdk.aries_rfc.Invitation = event.message
            their_vk = inv.recipient_keys[0]
            endpoint_uid = hashlib.sha256(their_vk.encode('utf-8')).hexdigest()
            # Configure AriesRFC 0160 state machine
            state_machine = sirius_sdk.aries_rfc.Invitee(
                me=sirius_sdk.Pairwise.Me(did=DID, verkey=KEYPAIR[0]),
                my_endpoint=sirius_sdk.Endpoint(address='ws://', routing_keys=[]),
                coprotocol=ClientWebSocketCoProtocol(
                    ws=websocket, my_keys=KEYPAIR, their_verkey=their_vk
                )
            )
            # Declare MediatorService endpoint via DIDDoc
            did_doc = ConnProtocolMessage.build_did_doc(did=DID, verkey=KEYPAIR[0], endpoint=WS_ENDPOINT)
            did_doc_extra = {'service': did_doc['service']}
            mediator_service_endpoint = WEBROOT
            if mediator_service_endpoint.startswith('https://'):
                mediator_service_endpoint = mediator_service_endpoint.replace('https://', 'wss://')
            elif mediator_service_endpoint.startswith('http://'):
                mediator_service_endpoint = mediator_service_endpoint.replace('http://', 'ws://')
            else:
                raise RuntimeError('Invalid WEBROOT url')
            mediator_service_endpoint = urljoin(mediator_service_endpoint, endpoint_uid)
            did_doc_extra['service'].append({
                "id": 'did:peer:' + DID + ";indy",
                "type": MEDIATOR_SERVICE_TYPE,
                "recipientKeys": [],
                "serviceEndpoint": mediator_service_endpoint,
            })
            # configure redis pubsub infrastructure for endpoint
            redis_server = await choice_redis_server_address()
            await ensure_endpoint_exists(
                db=db,
                uid=endpoint_uid,
                redis_pub_sub=f'redis://{redis_server}/{endpoint_uid}',
                verkey=their_vk
            )
            # Run AriesRFC-0160 state-machine
            success, p2p = await state_machine.create_connection(
                invitation=inv, my_label=MEDIATOR_LABEL, did_doc=did_doc_extra
            )
            if success:
                # If all OK, store p2p and metadata info to database
                await sirius_sdk.PairwiseList.ensure_exists(p2p)
                # Try to extract firebase device_id
                fcm_device_id = None
                if p2p.their.did_doc:
                    their_services = p2p.their.did_doc.get('service', [])
                    for service in their_services:
                        if service['type'] == FCM_SERVICE_TYPE:
                            fcm_device_id = service['serviceEndpoint']
                            break
                await ensure_agent_exists(
                    db, did=p2p.their.did, verkey=p2p.their.verkey, metadata=p2p.metadata, fcm_device_id=fcm_device_id
                )
                agent = await load_agent(db=db, did=p2p.their.did)
                await ensure_endpoint_exists(
                    db=db,
                    uid=endpoint_uid,
                    agent_id=agent['id'],
                    verkey=p2p.their.verkey,
                    fcm_device_id=fcm_device_id
                )
        elif isinstance(event.message, CoordinateMediationMessage):
            # Restore recipient agent context
            p2p = event.pairwise
            if p2p is None:
                # TODO: raise error and problem_report
                pass
            router_endpoint = await load_endpoint_via_verkey(db, p2p.their.verkey)
            # Agent manage mediation services and endpoints
            if isinstance(event.message, MediateRequest):
                ''' Request from the recipient to the mediator, asking for the permission (and routing information) to 
                    publish the endpoint as a mediator.
                    
                Details: https://github.com/hyperledger/aries-rfcs/tree/master/features/0211-route-coordination#mediation-request'''
                resp = MediateGrant(
                    endpoint=urljoin(WEBROOT, router_endpoint['uid']),
                    routing_keys=[]
                )
                await listener.response(for_event=event, message=resp)
            elif isinstance(event.message, KeylistUpdate):
                req: KeylistUpdate = event.message
                for upd in req['updates']:
                    if upd['action'] == 'add':
                        pass
                    elif upd['action'] == 'remove':
                        pass


@router.post('/{{endpoint_uid}}')
async def endpoint(request: Request, endpoint_uid: str):
    pass
