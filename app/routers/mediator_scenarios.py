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
from app.core.repo import Repo
from app.core.global_config import GlobalConfig
from app.core.redis import RedisPull
from app.core.rfc import extract_key as rfc_extract_key, ensure_is_key as rfc_ensure_is_key
from app.core.websocket_listener import WebsocketListener
from app.settings import KEYPAIR, DID
from app.utils import build_endpoint_url

from .utils import build_did_doc_extra, post_create_pairwise


class BasicMessageProblemReport(AriesProblemReport, metaclass=RegisterMessage):
    PROTOCOL = BasicMessage.PROTOCOL


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
                request.validate()
                ws_endpoint, endpoint_uid, did_doc_extra = await build_did_doc_extra(
                    repo=repo,
                    their_did=request.did_doc['id'],
                    their_verkey=event.sender_verkey
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
                    resp = MediateGrant(
                        endpoint=urljoin(webroot, build_endpoint_url(router_endpoint['uid'])),
                        routing_keys=[f"did:key:{k['key']}" for k in keys]
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
            else:
                typ = event.message.get('@type')
                raise RuntimeError(f'Unknown protocl message with @type: "{typ}"')
        except Exception as e:
            report = BasicMessageProblemReport(problem_code='1', explain=str(e))
            await listener.response(for_event=event, message=report)
            logging.exception('Onboarding...')


async def endpoint_processor(websocket: WebSocket, endpoint_uid: str, repo: Repo):

    async def redis_listener(redis_pub_sub: str):
        # Read from redis channel in infinite loop
        pulls = RedisPull()

        listener = pulls.listen(address=redis_pub_sub)
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
        report = BasicMessageProblemReport(problem_code='1', explain=f'Unknown endpoint with id: {endpoint_uid}')
        await websocket.send_bytes(json.dumps(report).encode())
        await websocket.close()
