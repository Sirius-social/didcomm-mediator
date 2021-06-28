from fastapi import APIRouter, WebSocket, Request


router = APIRouter(
    prefix="",
    tags=["relay"],
)


@router.websocket("/")
async def onboard(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({'ok': True})


@router.post('/')
async def endpoint(request: Request):
    pass


@router.post('/{{agent_id}}')
async def endpoint(request: Request, agent_id: str):
    pass
