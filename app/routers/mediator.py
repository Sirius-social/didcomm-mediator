import json
import logging

from typing import List

from databases import Database
from fastapi import APIRouter, Request, Depends, HTTPException, WebSocket

from app.core.repo import Repo
from app.core.singletons import GlobalMemcachedClient, GlobalRedisChannelsCache
from app.core.redis import RedisPush, RedisConnectionError, choice_server_address
from app.utils import build_invitation, extract_content_type, change_redis_server
from app.core.firebase import FirebaseMessages
from app.dependencies import get_db
from app.settings import ENDPOINTS_PATH_PREFIX, WS_PATH_PREFIX
from .mediator_scenarios import onboard as scenario_onboard, endpoint_processor as scenario_endpoint


router = APIRouter(
    prefix="",
    tags=["mediator"],
)

EXPECTED_CONTENT_TYPES = ['application/ssi-agent-wire', 'application/json']


@router.websocket(f"/{WS_PATH_PREFIX}")
async def onboard(websocket: WebSocket, db: Database = Depends(get_db)):
    logging.debug('')
    logging.debug('******************************')
    logging.debug('*** onboard handler call ***')
    logging.debug('*****************************')
    await websocket.accept()
    repo = Repo(db, memcached=GlobalMemcachedClient.get())
    # Parse query params
    endpoint_uid = websocket.query_params.get('endpoint')
    logging.debug(f'endpoint_uid: {endpoint_uid}')

    if endpoint_uid is None:
        await scenario_onboard(websocket, repo)
    else:
        await scenario_endpoint(websocket, endpoint_uid, repo)
    logging.debug('\n**************************')
    logging.debug('*****************************')


@router.post(f'/{ENDPOINTS_PATH_PREFIX}/{{endpoint_uid}}')
async def endpoint(request: Request, endpoint_uid: str, db: Database = Depends(get_db)):

    logging.debug('')
    logging.debug('*********************************************************')
    logging.debug(f'******* Endpoint handler for endpoint_uid: {endpoint_uid} ******')
    logging.debug('*********************************************************')
    content_type = extract_content_type(request)
    if content_type not in EXPECTED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail='Expected content types: %s' % str(EXPECTED_CONTENT_TYPES))

    repo = Repo(db=db, memcached=GlobalMemcachedClient.get())
    pushes = RedisPush(db, memcached=GlobalMemcachedClient.get(), channels_cache=GlobalRedisChannelsCache.get())
    endpoint_fields = await repo.load_endpoint(endpoint_uid)

    logging.debug('endpoint_fields: ' + repr(endpoint_fields))

    payload = b''
    async for chunk in request.stream():
        payload += chunk
    if endpoint_fields:
        message = json.loads(payload.decode())
        try:
            logging.debug('push message to websocket connection')
            success = await pushes.push(endpoint_uid, message, ttl=5)
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
            if fcm_device_id:
                if FirebaseMessages.enabled():
                    logging.debug('push message via FCM')
                    success = await FirebaseMessages.send(device_id=fcm_device_id, msg=message)
                    logging.debug(f'push operation returned success: {success}')
                    if success:
                        return
                    else:
                        raise HTTPException(status_code=410, detail='Recipient is registered but is not active')
                else:
                    raise HTTPException(status_code=421, detail='Firebase cloud messaging is not configured on server-side')
            else:
                raise HTTPException(status_code=410, detail='Recipient is registered but is not active')
    else:
        raise HTTPException(status_code=404, detail='Not Found')


@router.get('/invitation')
async def invitation():
    return build_invitation()
