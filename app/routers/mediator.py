import json
import logging

from typing import List

from databases import Database
from sirius_sdk.encryption import unpack_message
from sse_starlette.sse import EventSourceResponse
from fastapi import APIRouter, Request, Depends, HTTPException, WebSocket

import settings
from app.core.repo import Repo
from app.core.global_config import GlobalConfig
from app.core.singletons import GlobalMemcachedClient, GlobalRedisChannelsCache
from app.core.redis import RedisPush, RedisConnectionError, choice_server_address
from app.utils import extract_content_type, change_redis_server, extract_recipients
from app.core.firebase import FirebaseMessages
from app.core.forward import FORWARD
from app.dependencies import get_db
from app.settings import ENDPOINTS_PATH_PREFIX, WS_PATH_PREFIX, LONG_POLLING_PATH_PREFIX, ROUTER_PATH
from .mediator_scenarios import onboard as scenario_onboard, \
    endpoint_processor as scenario_endpoint, endpoint_long_polling, listen_events


router = APIRouter(
    prefix="",
    tags=["mediator"],
)

EXPECTED_CONTENT_TYPES = [
    'application/ssi-agent-wire', 'application/json',
    'application/didcomm-envelope-enc', 'application/didcomm-encrypted+json'
]


@router.websocket(f"/{WS_PATH_PREFIX}")
async def onboard(websocket: WebSocket, db: Database = Depends(get_db)):
    logging.debug('')
    logging.debug('******************************')
    logging.debug('*** onboard handler call ***')
    logging.debug('*****************************')
    await websocket.accept()
    repo = Repo(db, memcached=GlobalMemcachedClient.get())
    cfg = GlobalConfig(db, memcached=GlobalMemcachedClient.get())
    # Parse query params
    endpoint_uid = websocket.query_params.get('endpoint')
    logging.debug(f'endpoint_uid: {endpoint_uid}')

    if endpoint_uid is None:
        await scenario_onboard(websocket, repo, cfg)
    else:
        await scenario_endpoint(websocket, endpoint_uid, repo)
    logging.debug('\n**************************')
    logging.debug('*****************************')


@router.get(f"/{LONG_POLLING_PATH_PREFIX}")
async def long_polling(request: Request, db: Database = Depends(get_db)):
    endpoint_uid = request.query_params.get('endpoint')
    logging.debug(f'endpoint_uid: {endpoint_uid}')
    if endpoint_uid is None:
        raise HTTPException(status_code=404, detail='Empty endpoint id')
    else:
        repo = Repo(db, memcached=GlobalMemcachedClient.get())
        event_generator = endpoint_long_polling(request, endpoint_uid, repo)
        return EventSourceResponse(event_generator)


async def post_to_device(payload, endpoint_fields: dict, db: Database):

    repo = Repo(db=db, memcached=GlobalMemcachedClient.get())
    pushes = RedisPush(db, memcached=GlobalMemcachedClient.get(), channels_cache=GlobalRedisChannelsCache.get())

    message = json.loads(payload.decode())
    try:
        logging.debug('push message to websocket connection')
        success = await pushes.push(endpoint_fields['uid'], message, ttl=5)
        logging.debug(f'push operation returned success: {success}')
    except RedisConnectionError as e:
        success = False
        logging.exception('Error while push message via redis')
        # Try select other redis server
        try:
            redis_server = await choice_server_address()
            unreachable_redis_pub_sub = endpoint_fields['redis_pub_sub']
            new_redis_pub_sub = change_redis_server(unreachable_redis_pub_sub, redis_server)
            endpoint_fields['redis_pub_sub'] = new_redis_pub_sub
            await repo.ensure_endpoint_exists(**endpoint_fields)
        except Exception as e:
            logging.exception('Error while reselect redis server')
            pass  # mute any exception
    if success:
        return
    else:
        fcm_device_id = endpoint_fields.get('fcm_device_id')
        logging.debug(f'fcm_device_id: {fcm_device_id}')
        if fcm_device_id:
            firebase = FirebaseMessages(db=db)
            fcm_enabled = await firebase.enabled()
            if fcm_enabled:
                logging.debug('FCM is enabled')
                logging.debug('push message via FCM')
                try:
                    success = await firebase.send(device_id=fcm_device_id, msg=message)
                except Exception:
                    success = False
                    logging.exception('FCM Error!')
                logging.debug(f'push operation returned success: {success}')
                if success:
                    return
                else:
                    raise HTTPException(status_code=410,
                                        detail='Recipient is registered but is not active with Firebase')
            else:
                raise HTTPException(status_code=421, detail='Firebase cloud messaging is not configured on server-side')
        else:
            raise HTTPException(status_code=410, detail='Recipient is registered but is not active')


@router.post(f'/{ENDPOINTS_PATH_PREFIX}/{{endpoint_uid}}', status_code=202)
async def endpoint(request: Request, endpoint_uid: str, db: Database = Depends(get_db)):

    logging.debug('')
    logging.debug('*********************************************************')
    logging.debug(f'******* Endpoint handler for endpoint_uid: {endpoint_uid} ******')
    logging.debug('*********************************************************')
    content_type = extract_content_type(request)
    if content_type not in EXPECTED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail='Expected content types: %s' % str(EXPECTED_CONTENT_TYPES))

    repo = Repo(db=db, memcached=GlobalMemcachedClient.get())
    endpoint_fields = await repo.load_endpoint(endpoint_uid)

    logging.debug('endpoint_fields: ' + repr(endpoint_fields))

    payload = b''
    async for chunk in request.stream():
        payload += chunk
    if endpoint_fields:
        await post_to_device(payload, endpoint_fields, db)
    else:
        raise HTTPException(status_code=404, detail='Not Found')


@router.post(f'/{ROUTER_PATH}', status_code=202)
async def routing(request: Request, db: Database = Depends(get_db)):
    logging.debug('')
    logging.debug('*********************************************************')
    logging.debug(f'******* Routing endpoint ******')
    logging.debug('*********************************************************')
    content_type = extract_content_type(request)
    if content_type not in EXPECTED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail='Expected content types: %s' % str(EXPECTED_CONTENT_TYPES))

    payload = b''
    async for chunk in request.stream():
        payload += chunk
    mediator_vk, mediator_sk = settings.KEYPAIR
    repo = Repo(db=db, memcached=GlobalMemcachedClient.get())
    try:
        recipients = extract_recipients(payload)
        recip_verkeys = [recp['header']['kid'] for recp in recipients if 'header' in recp.keys()]
        if mediator_vk in recip_verkeys:
            msg, sender_vk, recip_vk = unpack_message(payload, my_verkey=mediator_vk, my_sigkey=mediator_sk)
            fwd = json.loads(msg)
            if fwd.get('@type') != FORWARD:
                raise HTTPException(status_code=400, detail='Message partially decoded but forwarded message expected')
            route_to_vk = fwd.get('to', None)
            if not route_to_vk:
                raise HTTPException(status_code=400, detail='Expected "to" attribute in Forwarded message')
            msg = fwd.get('msg', None)
            if not msg:
                raise HTTPException(status_code=400, detail='Expected "msg" attribute in Forwarded message')
            endpoint_fields = await repo.load_endpoint_via_routing_key(route_to_vk)
            if endpoint_fields:
                await post_to_device(json.dumps(msg).encode(), endpoint_fields, db)
            else:
                raise HTTPException(status_code=400, detail='Unknown destination key')
        else:
            # Re-route to first known verkey
            for route_to_vk in recip_verkeys:
                endpoint_fields = await repo.load_endpoint_via_routing_key(route_to_vk)
                if endpoint_fields:
                    await post_to_device(payload, endpoint_fields, db)
                    return
            raise HTTPException(status_code=400, detail='No one of recipient keys registered')
    except:
        raise HTTPException(status_code=400, detail='Expected forwarded message in request body')


@router.websocket(f"/{WS_PATH_PREFIX}/events")
async def events(websocket: WebSocket, db: Database = Depends(get_db)):
    stream = websocket.query_params.get('stream')
    logging.debug('*****************************')
    logging.debug(f'stream: {stream}')
    logging.debug('*****************************')
    await websocket.accept()
    try:
        await listen_events(websocket, stream)
    finally:
        await websocket.close()
