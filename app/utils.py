import asyncio
import base64
import hashlib
import json
import threading
from urllib.parse import urljoin
from typing import Optional, Callable, Any

import sirius_sdk
from databases import Database
from fastapi import Request

from app.core.global_config import GlobalConfig
from app.core.singletons import GlobalMemcachedClient
from app.settings import WEBROOT, MEDIATOR_LABEL, KEYPAIR, ENDPOINTS_PATH_PREFIX, WS_PATH_PREFIX, LONG_POLLING_PATH_PREFIX


def extract_content_type(request: Request) -> Optional[str]:
    for header, value in request.headers.items():
        if header.lower() == 'content-type':
            return value
    return None


def build_ws_endpoint_addr() -> str:
    mediator_endpoint = WEBROOT
    if mediator_endpoint.startswith('https://'):
        mediator_endpoint = mediator_endpoint.replace('https://', 'wss://')
    elif mediator_endpoint.startswith('http://'):
        mediator_endpoint = mediator_endpoint.replace('http://', 'ws://')
    else:
        raise RuntimeError('Invalid WEBROOT url')
    mediator_endpoint = urljoin(mediator_endpoint, WS_PATH_PREFIX)
    return mediator_endpoint


async def async_build_ws_endpoint_addr(db: Database) -> Optional[str]:
    cfg = GlobalConfig(db, GlobalMemcachedClient.get())
    mediator_endpoint = await cfg.get_webroot()
    if mediator_endpoint:
        if mediator_endpoint.startswith('https://'):
            mediator_endpoint = mediator_endpoint.replace('https://', 'wss://')
        elif mediator_endpoint.startswith('http://'):
            mediator_endpoint = mediator_endpoint.replace('http://', 'ws://')
        else:
            raise RuntimeError('Invalid WEBROOT url')
        mediator_endpoint = urljoin(mediator_endpoint, WS_PATH_PREFIX)
        return mediator_endpoint
    else:
        return None


async def async_build_long_polling_addr(db: Database) -> Optional[str]:
    cfg = GlobalConfig(db, GlobalMemcachedClient.get())
    mediator_endpoint = await cfg.get_webroot()
    if mediator_endpoint:
        mediator_endpoint = urljoin(mediator_endpoint, LONG_POLLING_PATH_PREFIX)
        return mediator_endpoint
    else:
        return None


def build_invitation(id_: str = None, pass_endpoint_empty: bool = False) -> dict:

    if pass_endpoint_empty:
        endpoint = ''
    else:
        endpoint = build_ws_endpoint_addr()

    return sirius_sdk.aries_rfc.Invitation(
        id_=id_,
        label=MEDIATOR_LABEL,
        recipient_keys=[KEYPAIR[0]],
        endpoint=endpoint,
        routing_keys=[]
    )


async def async_build_invitation(db: Database, id_: str = None) -> dict:

    invitation = build_invitation(id_, pass_endpoint_empty=True)
    actual_endpoint = await async_build_ws_endpoint_addr(db)
    invitation['endpoint'] = actual_endpoint

    return sirius_sdk.aries_rfc.Invitation(
        id_=id_,
        label=MEDIATOR_LABEL,
        recipient_keys=[KEYPAIR[0]],
        endpoint=actual_endpoint,
        routing_keys=[]
    )


def build_endpoint_url(endpoint_uid: str) -> str:
    return f'/{ENDPOINTS_PATH_PREFIX}/{endpoint_uid}'


def make_group_id_mangled(group_id: str, endpoint_uid: str) -> str:
    return f'{endpoint_uid}/{group_id}'


def change_redis_server(pub_sub: str, new_redis_server: str) -> str:
    channel_name = pub_sub.split('/')[-1]
    return f'{new_redis_server}/{channel_name}'


def hash_string(s: str) -> str:
    m = hashlib.md5()
    m.update(s.encode())
    return m.hexdigest()


class LoopInThread(threading.Thread):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_ready = asyncio.Event()
        self.on_ready.clear()
        self.loop: Optional[asyncio.BaseEventLoop] = None

    def run(self):
        self.loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(self.loop)
        self.on_ready.set()
        self.loop.run_forever()

    def kill(self):
        if self.loop:
            self.loop.stop()

    @classmethod
    async def execute(cls, func: Callable, *args, **kwargs) -> Any:
        inst = LoopInThread()
        inst.start()
        await inst.on_ready.wait()

        result = None
        on_done = asyncio.Event()
        on_done.clear()

        async def co():
            nonlocal result
            nonlocal on_done
            result = func(*args, **kwargs)
            on_done.set()

        asyncio.run_coroutine_threadsafe(co(), loop=inst.loop)
        await on_done.wait()
        return result


async def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    ret = await LoopInThread.execute(func, *args, **kwargs)
    return ret


def extract_recipients(jwe: bytes) -> list:
    jwe = json.loads(jwe.decode())
    protected = jwe['protected']
    payload = json.loads(base64.b64decode(protected))
    recipients = payload.get('recipients', [])
    return recipients