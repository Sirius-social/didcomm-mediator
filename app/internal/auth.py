import json
import uuid
from typing import Optional

from fastapi import Request, Response

from app.core.singletons import GlobalMemcachedClient


SESSION_COOKIE_KEY = 'didcomm-app-session-id'
SESSION_EXPIRE_SECS = 60*60  # 1 hour


async def auth_user(request: Request) -> Optional[dict]:
    """Return user if authorized else None"""
    session_id = request.cookies.get(SESSION_COOKIE_KEY)
    if session_id:
        cache = GlobalMemcachedClient.get()
        user_bytes, _ = await cache.get(session_id.encode())
        if user_bytes:
            user = json.loads(user_bytes.decode())
            # Refresh cache expiration
            await cache.set(session_id.encode(), user_bytes, exptime=SESSION_EXPIRE_SECS)
            # return user data
            return user
        else:
            return None
    else:
        return None


async def login(response: Response, user: dict):
    username = user.get('username')
    if username:
        cache = GlobalMemcachedClient.get()
        session_id = uuid.uuid4().hex
        await cache.set(session_id.encode(), json.dumps(user).encode(), exptime=SESSION_EXPIRE_SECS)
        response.set_cookie(SESSION_COOKIE_KEY, session_id)
    else:
        raise RuntimeError('Unexpected user data')


async def logout(request: Request, response: Response):
    session_id = request.cookies.get(SESSION_COOKIE_KEY)
    if session_id:
        response.delete_cookie(session_id)
        cache = GlobalMemcachedClient.get()
        await cache.delete(session_id.encode())
