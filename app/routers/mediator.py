from databases import Database
from fastapi import APIRouter, Request, Depends, HTTPException, WebSocket

from app.core.repo import Repo
from app.core.singletons import GlobalMemcachedClient
from app.core.redis import RedisPush
from app.utils import build_invitation
from app.dependencies import get_db
from app.settings import ENDPOINTS_PATH_PREFIX
from .mediator_scenarios import onboard as scenario_onboard, endpoint_processor as scenario_endpoint


router = APIRouter(
    prefix="",
    tags=["mediator"],
)


WS_ENDPOINT = 'ws://'


@router.websocket("/")
async def onboard(websocket: WebSocket, db: Database = Depends(get_db)):
    await websocket.accept()
    repo = Repo(db, memcached=GlobalMemcachedClient.get())

    # Parse query params
    endpoint_uid = websocket.query_params.get('endpoint')

    if endpoint_uid is None:
        await scenario_onboard(websocket, repo)
    else:
        await scenario_endpoint(websocket, endpoint_uid, repo)


@router.post(f'/{ENDPOINTS_PATH_PREFIX}/{{endpoint_uid}}')
async def endpoint(request: Request, endpoint_uid: str, db: Database = Depends(get_db)):
    repo = Repo(db=db, memcached=GlobalMemcachedClient.get())
    pushes = RedisPush(db)
    data = await repo.load_endpoint(endpoint_uid)
    if data:
        await pushes.push(endpoint_uid, {}, ttl=5)
    else:
        raise HTTPException(status_code=404, detail='Not Found')


@router.get('/invitation')
async def invitation():
    return build_invitation()
