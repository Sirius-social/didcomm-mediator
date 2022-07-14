import asyncio
import hashlib
import json
import logging
from urllib.parse import urljoin
from typing import Optional, Dict

import sirius_sdk
from sirius_sdk.agent.listener import Event
from fastapi import WebSocket, Request, HTTPException, WebSocketDisconnect
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol.messages import ConnProtocolMessage
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import *
from sirius_sdk.agent.aries_rfc.base import RegisterMessage, AriesProblemReport
from sirius_sdk.agent.aries_rfc.feature_0095_basic_message.messages import Message as BasicMessage

import settings
from app.core.coprotocols import ClientWebSocketCoProtocol
from app.core.repo import Repo
from app.core.global_config import GlobalConfig
from app.core.redis import RedisPull, AsyncRedisChannel
from app.core.rfc import extract_key as rfc_extract_key, ensure_is_key as rfc_ensure_is_key
from app.core.websocket_listener import WebsocketListener
from app.core.bus import Bus
from app.settings import KEYPAIR, DID
from app.utils import build_endpoint_url
from rfc.coprotocols import *

from .utils import build_did_doc_extra, post_create_pairwise, build_consistent_endpoint_uid, \
    build_protocol_topic


URI_QUEUE_TRANSPORT = 'didcomm:transport/queue'


class BasicMessageProblemReport(AriesProblemReport, metaclass=RegisterMessage):
    PROTOCOL = BasicMessage.PROTOCOL


async def protocol_listener(
        topic: str, binding_id: str, ws: WebSocket, on: asyncio.Event, p2p: sirius_sdk.Pairwise = None
):
    bus = Bus()
    async for payload in bus.listen(topic, on=on):
        event = BusEvent(payload=payload, binding_id=binding_id)
        if p2p:
            packed = await sirius_sdk.Crypto.pack_message(
                message=json.dumps(event),
                recipient_verkeys=[p2p.their.verkey],
                sender_verkey=p2p.me.verkey
            )
            await ws.send_bytes(packed)
        else:
            payload = json.dumps(event).encode()
            await ws.send_bytes(payload)


async def onboard(websocket: WebSocket, repo: Repo, cfg: GlobalConfig):
    """Scenario for onboarding procedures:
      - establish Pairwise (P2P)
      - Trust Ping
      - Mediator coordination protocol AriesRFC 0211

    :param websocket: websocket session  with client
    :param repo: Repository to get access to persistent data
    :param: cfg: configurations
    """
    # Wrap parsing and unpacking enc_messages in listener
    inbound_listener: Optional[asyncio.Future] = None
    protocols_bus = Bus()
    group_id = None
    listener = WebsocketListener(ws=websocket, my_keys=KEYPAIR)
    protocols_listeners: Dict[str, asyncio.Task] = {}
    try:
        async for event in listener:
            try:
                if event is None:  # Stop listening: websocket die
                    await websocket.close()
                    return
                logging.debug('========= EVENT ============')
                logging.debug(json.dumps(event, indent=2, sort_keys=True))
                logging.debug('============================')

                if isinstance(event.message, sirius_sdk.aries_rfc.Ping):
                    # Agent sent Ping to check connection
                    ping: sirius_sdk.aries_rfc.Ping = event.message
                    if ping.response_requested:
                        pong = sirius_sdk.aries_rfc.Pong(ping_id=ping.id)
                        await listener.response(for_event=event, message=pong)
                elif isinstance(event.message, sirius_sdk.aries_rfc.ConnRequest):
                    # Agent was start p2p establish
                    request: sirius_sdk.aries_rfc.ConnRequest = event.message
                    request.validate()

                    their_services = request.did_doc.get('service', [])
                    services_with_group_id = [service for service in their_services if 'group_id' in service]
                    if services_with_group_id:
                        group_id = services_with_group_id[0]['group_id']

                    ws_endpoint, endpoint_uid, did_doc_extra = await build_did_doc_extra(
                        repo=repo,
                        their_did=request.did_doc['id'],
                        their_verkey=event.sender_verkey,
                        group_id=group_id
                    )
                    # Configure AriesRFC 0160 state machine
                    state_machine = sirius_sdk.aries_rfc.Inviter(
                        me=sirius_sdk.Pairwise.Me(did=DID, verkey=KEYPAIR[0]),
                        connection_key=event.recipient_verkey,
                        my_endpoint=sirius_sdk.Endpoint(address=ws_endpoint, routing_keys=[]),
                        coprotocol=ClientWebSocketCoProtocol(
                            ws=websocket, my_keys=KEYPAIR, their_verkey=event.sender_verkey
                        )
                    )
                    # Run AriesRFC-0160 state-machine
                    success, p2p = await state_machine.create_connection(
                        request=request, did_doc=did_doc_extra
                    )
                    if success:
                        # If all OK, store p2p and metadata info to database
                        await sirius_sdk.PairwiseList.ensure_exists(p2p)
                        await post_create_pairwise(repo, p2p, endpoint_uid)

                        # If recipient supports Queue Transport then it can receive inbound
                        # via same websocket connection
                        their_services = p2p.their.did_doc.get('service', [])
                        if any([service['serviceEndpoint'] == URI_QUEUE_TRANSPORT for service in their_services]):
                            if inbound_listener and not inbound_listener.done():
                                # terminate all task
                                inbound_listener.cancel()

                            stream = build_consistent_endpoint_uid(p2p.their.did)
                            inbound_listener = asyncio.ensure_future(
                                endpoint_processor(websocket, stream, repo, False, group_id=group_id)
                            )
                        else:
                            if inbound_listener and not inbound_listener.done():
                                inbound_listener.cancel()
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
                        webroot = await cfg.get_webroot()
                        keys = await repo.list_routing_key(router_endpoint['uid'])
                        if keys:
                            mediator_vk = KEYPAIR[0]
                            resp = MediateGrant(
                                endpoint=urljoin(webroot, settings.ROUTER_PATH),
                                routing_keys=[f"did:key:{mediator_vk}"]
                            )
                        else:
                            resp = MediateGrant(
                                endpoint=urljoin(webroot, build_endpoint_url(router_endpoint['uid'])),
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
                                updated.append(KeylistAddAction(rfc_ensure_is_key(key), result='success'))
                            elif upd['action'] == 'remove':
                                key = rfc_extract_key(upd['recipient_key'])
                                await repo.remove_routing_key(router_endpoint['uid'], key)
                                updated.append(KeylistRemoveAction(rfc_ensure_is_key(key), result='success'))
                            else:
                                raise RuntimeError(f"Unexpected action: {upd['action']}")
                        resp = KeylistUpdateResponce(updated=updated)
                        await listener.response(for_event=event, message=resp)
                    elif isinstance(event.message, KeylistQuery):
                        req: KeylistQuery = event.message
                        offset = req.get('paginate', {}).get('offset', None) or 0
                        limit = req.get('paginate', {}).get('limit', None) or 1000000
                        keys = await repo.list_routing_key(router_endpoint['uid'])
                        keys = [rfc_ensure_is_key(k['key']) for k in keys]
                        paged_keys = keys[offset:limit]
                        resp = Keylist(
                            keys=paged_keys,
                            count=len(paged_keys),
                            offset=offset,
                            remaining=len(keys)-len(paged_keys)-offset
                        )
                        resp['keys'] = [{'recipient_key': f'did:key:{k}'} for k in paged_keys]
                        await listener.response(for_event=event, message=resp)
                elif isinstance(event.message, BusOperation):
                    op: BusOperation = event.message
                    if event.pairwise:
                        their_did = event.pairwise.their.did
                    else:
                        their_did = '*'
                    if isinstance(op, BusSubscribeRequest):
                        if op.cast.thid:
                            binding_id = op.cast.thid
                        else:
                            if not op.cast.validate():
                                await listener.response(
                                    for_event=event,
                                    message=BusProblemReport(
                                        problem_code='invalid_cast',
                                        explain='Invalid cast field, check it'
                                    )
                                )
                            binding_id = json.dumps(op.cast.as_json(), sort_keys=True)
                        if isinstance(binding_id, list):
                            binding_id = [s for s in binding_id]
                        else:
                            binding_id = binding_id
                        resp = BusBindResponse(binding_id=binding_id, active=True, client_id=op.client_id)
                        for bid in ([binding_id] if isinstance(binding_id, str) else binding_id):
                            topic = build_protocol_topic(their_did, bid)
                            tsk = protocols_listeners.get(bid, None)
                            if tsk and tsk.done():
                                tsk = None
                            if not tsk:
                                on = asyncio.Event()
                                tsk = asyncio.create_task(
                                    protocol_listener(topic=topic, binding_id=bid, ws=websocket, on=on, p2p=event.pairwise)
                                )
                                tsk.client_id = op.client_id
                                protocols_listeners[bid] = tsk
                                await on.wait()
                        if protocols_listeners and group_id is None:
                            if inbound_listener and not inbound_listener.done():
                                inbound_listener.cancel()
                        await listener.response(for_event=event, message=resp)
                    elif isinstance(op, BusUnsubscribeRequest):
                        processed_binding_id = []
                        binding_ids = [op.binding_id] if isinstance(op.binding_id, str) else op.binding_id
                        if binding_ids is None:
                            binding_ids = []
                        if op.client_id:
                            binding_ids.extend([bid for bid, tsk in protocols_listeners.items() if tsk.client_id == op.client_id])
                        if binding_ids:
                            for bid in binding_ids:
                                if bid in protocols_listeners:
                                    tsk = protocols_listeners.get(bid, None)
                                    if tsk and not tsk.done():
                                        tsk.cancel()
                                    del protocols_listeners[bid]
                                    processed_binding_id.append(bid)
                        else:
                            for tsk in protocols_listeners.values():
                                if tsk and not tsk.done():
                                    tsk.cancel()
                            processed_binding_id = list(protocols_listeners.keys())
                            protocols_listeners.clear()
                        if len(processed_binding_id) == 1:
                            processed_binding_id = processed_binding_id[0]
                        if op.need_answer is True or op.aborted is True:
                            resp = BusBindResponse(
                                binding_id=processed_binding_id, active=False,
                                aborted=op.aborted, client_id=op.client_id
                            )
                            await listener.response(for_event=event, message=resp)
                    elif isinstance(op, BusPublishRequest):
                        topic = build_protocol_topic(their_did, op.binding_id)
                        payload = op.payload
                        if payload:
                            if isinstance(payload, bytes):
                                recipients_num = await protocols_bus.publish(topic, payload)
                                resp = BusPublishResponse(binding_id=op.binding_id, recipients_num=recipients_num)
                            else:
                                resp = BusProblemReport(
                                    problem_code='invalid_payload',
                                    explain='Expected "payload" is base64 encoded bytearray'
                                )
                        else:
                            resp = BusProblemReport(problem_code='empty_payload', explain='Expected "payload" is filled')
                        await listener.response(for_event=event, message=resp)
                else:
                    typ = event.message.get('@type')
                    raise RuntimeError(f'Unknown protocl message with @type: "{typ}"')
            except Exception as e:
                report = BasicMessageProblemReport(problem_code='1', explain=str(e))
                await listener.response(for_event=event, message=report)
                logging.exception('Onboarding...')
    finally:
        # Clean resources
        if inbound_listener and not inbound_listener.done():
            inbound_listener.cancel()
        for tsk in protocols_listeners.values():
            if not tsk.done():
                tsk.cancel()


async def endpoint_processor(
        websocket: WebSocket, endpoint_uid: str, repo: Repo, exit_on_disconnect: bool = True, group_id: str = None
):

    async def redis_listener(redis_pub_sub: str):
        # Read from redis channel in infinite loop
        pulls = RedisPull()

        listener = pulls.listen(address=redis_pub_sub, group_id=group_id)
        async for not_closed, request in listener:
            logging.debug(f'++++++++++++ not_closed: {not_closed}')
            if not_closed:
                req: RedisPull.Request = request
                logging.debug('++++++++++++ send message via websocket ')
                await websocket.send_json(request.message)
                logging.debug('+++++++++++ message was sent via websocket ')
                await req.ack()
                logging.debug('++++++++++ message acked ')
            else:
                break

    logging.debug('')
    logging.debug('++++++++++++++++++++++++++++++++++++++++++++++++++')
    logging.debug(f'+++ Redis listener for endpoint_uid: {endpoint_uid}')
    logging.debug('++++++++++++++++++++++++++++++++++++++++++++++++++')
    data = await repo.load_endpoint(endpoint_uid)
    logging.debug('websocket endpoint data: ' + repr(data))
    if data and data.get('redis_pub_sub'):
        coro = redis_listener(data['redis_pub_sub'])
        if exit_on_disconnect:
            fut = asyncio.ensure_future(coro)
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
            await coro
    else:
        report = BasicMessageProblemReport(problem_code='1', explain=f'Unknown endpoint with id: {endpoint_uid}')
        await websocket.send_bytes(json.dumps(report).encode())
        await websocket.close()


async def endpoint_long_polling(request: Request, endpoint_uid: str, repo: Repo, group_id: str = None):
    logging.debug('')
    logging.debug('++++++++++++++++++++++++++++++++++++++++++++++++++')
    logging.debug(f'+++ Redis listener for endpoint_uid: {endpoint_uid}')
    logging.debug('++++++++++++++++++++++++++++++++++++++++++++++++++')
    data = await repo.load_endpoint(endpoint_uid)
    logging.debug('long-polling endpoint data: ' + repr(data))
    if data and data.get('redis_pub_sub'):
        # Read from redis channel in infinite loop
        pulls = RedisPull()
        listener = pulls.listen(address=data['redis_pub_sub'], group_id=group_id)

        async def wait_for_close_conn():
            while True:
                if await request.is_disconnected():
                    logging.debug('Request disconnected')
                    await listener.close()
                    return

        fut = asyncio.ensure_future(wait_for_close_conn())
        try:
            async for not_closed, req in listener:
                logging.debug(f'++++++++++++ not_closed: {not_closed}')
                if not_closed:
                    req: RedisPull.Request = req
                    logging.debug('++++++++++++ yield message')
                    line = json.dumps(req.message)
                    yield line
                    await req.ack()
                    logging.debug('++++++++++ message acked')
                else:
                    break
        finally:
            fut.cancel()
    else:
        report = BasicMessageProblemReport(problem_code='1', explain=f'Unknown endpoint with id: {endpoint_uid}')
        line = json.dumps(report)
        yield line


async def listen_events(websocket: WebSocket, stream: str):
    ch = AsyncRedisChannel(address=stream)
    while True:
        ok, data = await ch.read(timeout=None)
        if ok:
            await websocket.send_json(data)
        else:
            return
