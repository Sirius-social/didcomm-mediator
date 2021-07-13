import asyncio
import hashlib
import json
import logging
from urllib.parse import urljoin

import sirius_sdk
from fastapi import WebSocket, Request, HTTPException, WebSocketDisconnect
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol.messages import ConnProtocolMessage
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import *
from sirius_sdk.agent.aries_rfc.base import RegisterMessage, AriesProblemReport
from sirius_sdk.agent.aries_rfc.feature_0095_basic_message.messages import Message as BasicMessage

from app.core.coprotocols import ClientWebSocketCoProtocol
from app.core.redis import choice_server_address as choice_redis_server_address
from app.core.repo import Repo
from app.core.redis import RedisPull
from app.core.rfc import extract_key as rfc_extract_key
from app.core.websocket_listener import WebsocketListener
from app.settings import KEYPAIR, DID, WEBROOT, MEDIATOR_SERVICE_TYPE, FCM_SERVICE_TYPE
from app.utils import build_ws_endpoint_addr, build_endpoint_url


class BasicMessageProblemReport(AriesProblemReport, metaclass=RegisterMessage):
    PROTOCOL = BasicMessage.PROTOCOL


async def onboard(websocket: WebSocket, repo: Repo):
    """Scenario for onboarding procedures:
      - establish Pairwise (P2P)
      - Trust Ping
      - Mediator coordination protocol AriesRFC 0211

    :param websocket: websocket session  with client
    :param repo: Repository to get access to persistent data
    """
    # Wrap parsing and unpacking enc_messages in listener
    listener = WebsocketListener(ws=websocket, my_keys=KEYPAIR)
    async for event in listener:
        try:
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
            elif isinstance(event.message, sirius_sdk.aries_rfc.ConnRequest):
                # Agent was start p2p establish
                request: sirius_sdk.aries_rfc.ConnRequest = event.message
                endpoint_uid = hashlib.sha256(event.sender_verkey.encode('utf-8')).hexdigest()
                # Configure AriesRFC 0160 state machine
                state_machine = sirius_sdk.aries_rfc.Inviter(
                    me=sirius_sdk.Pairwise.Me(did=DID, verkey=KEYPAIR[0]),
                    connection_key=event.recipient_verkey,
                    my_endpoint=sirius_sdk.Endpoint(address=build_ws_endpoint_addr(), routing_keys=[]),
                    coprotocol=ClientWebSocketCoProtocol(
                        ws=websocket, my_keys=KEYPAIR, their_verkey=event.sender_verkey
                    )
                )
                # Declare MediatorService endpoint via DIDDoc
                did_doc = ConnProtocolMessage.build_did_doc(did=DID, verkey=KEYPAIR[0], endpoint=build_ws_endpoint_addr())
                did_doc_extra = {'service': did_doc['service']}
                mediator_service_endpoint = build_ws_endpoint_addr()
                mediator_service_endpoint = urljoin(mediator_service_endpoint, f'?endpoint={endpoint_uid}')
                did_doc_extra['service'].append({
                    "id": 'did:peer:' + DID + ";indy",
                    "type": MEDIATOR_SERVICE_TYPE,
                    "recipientKeys": [],
                    "serviceEndpoint": mediator_service_endpoint,
                })
                # configure redis pubsub infrastructure for endpoint
                redis_server = await choice_redis_server_address()
                await repo.ensure_endpoint_exists(
                    uid=endpoint_uid,
                    redis_pub_sub=f'redis://{redis_server}/{endpoint_uid}',
                    verkey=event.sender_verkey
                )
                # Run AriesRFC-0160 state-machine
                success, p2p = await state_machine.create_connection(
                    request=request, did_doc=did_doc_extra
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
                    await repo.ensure_agent_exists(
                        did=p2p.their.did, verkey=p2p.their.verkey, metadata=p2p.metadata, fcm_device_id=fcm_device_id
                    )
                    agent = await repo.load_agent(did=p2p.their.did)
                    await repo.ensure_endpoint_exists(
                        uid=endpoint_uid,
                        agent_id=agent['id'],
                        verkey=p2p.their.verkey,
                        fcm_device_id=fcm_device_id
                    )
                else:
                    if state_machine.problem_report:
                        await listener.response(for_event=event, message=state_machine.problem_report)
            elif isinstance(event.message, CoordinateMediationMessage):
                # Restore recipient agent context
                p2p = event.pairwise
                if p2p is None:
                    raise RuntimeError(f'Pairwise (P2P) for Verkey: {event.sender_verkey} is empty, establish p2p connection at first!')
                router_endpoint = await repo.load_endpoint_via_verkey(p2p.their.verkey)
                # Agent manage mediation services and endpoints
                if isinstance(event.message, MediateRequest):
                    ''' Request from the recipient to the mediator, asking for the permission (and routing information) to 
                        publish the endpoint as a mediator.
                        
                    Details: https://github.com/hyperledger/aries-rfcs/tree/master/features/0211-route-coordination#mediation-request'''
                    resp = MediateGrant(
                        endpoint=urljoin(WEBROOT, build_endpoint_url(router_endpoint['uid'])),
                        routing_keys=[]
                    )
                    await listener.response(for_event=event, message=resp)
                elif isinstance(event.message, KeylistUpdate):
                    req: KeylistUpdate = event.message
                    updated = []
                    for upd in req['updates']:
                        if upd['action'] == 'add':
                            key = rfc_extract_key(upd['recipient_key'])
                            await repo.add_routing_key(router_endpoint['uid'], key)
                            updated.append(KeylistAddAction(key, result='success'))
                        elif upd['action'] == 'remove':
                            key = rfc_extract_key(upd['recipient_key'])
                            await repo.remove_routing_key(router_endpoint['uid'], key)
                            updated.append(KeylistRemoveAction(key, result='success'))
                        else:
                            raise RuntimeError(f"Unexpected action: {upd['action']}")
                    resp = KeylistUpdateResponce(updated=updated)
                    await listener.response(for_event=event, message=resp)
                elif isinstance(event.message, KeylistQuery):
                    req: KeylistQuery = event.message
                    offset = req.get('paginate', {}).get('offset', None) or 0
                    limit = req.get('paginate', {}).get('limit', None) or 1000000
                    keys = await repo.list_routing_key(router_endpoint['uid'])
                    keys = [k['key'] for k in keys]
                    paged_keys = keys[offset:limit]
                    resp = Keylist(
                        keys=paged_keys,
                        count=len(paged_keys),
                        offset=offset,
                        remaining=len(keys)-len(paged_keys)-offset
                    )
                    resp['keys'] = [{'recipient_key': f'did:key:{k}'} for k in paged_keys]
                    await listener.response(for_event=event, message=resp)
        except Exception as e:
            report = BasicMessageProblemReport(explain=str(e))
            await listener.response(for_event=event, message=report)


async def endpoint_processor(websocket: WebSocket, endpoint_uid: str, repo: Repo):

    async def redis_listener(redis_pub_sub: str):
        # Read from redis channel in infinite loop
        pulls = RedisPull()
        listener = pulls.listen(address=redis_pub_sub)
        async for not_closed, request in listener:
            if not_closed:
                req: RedisPull.Request = request
                await websocket.send_json(request.message)
                await req.ack()
            else:
                break

    data = await repo.load_endpoint(endpoint_uid)
    if data and data.get('redis_pub_sub'):
        fut = asyncio.ensure_future(redis_listener(data['redis_pub_sub']))
        try:
            try:
                while True:
                    await websocket.receive_bytes()
            except WebSocketDisconnect:
                pass
        finally:
            # websocket disconnected
            fut.cancel()
    else:
        # TODO: problem report
        await websocket.close()
