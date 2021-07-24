import json

from databases import Database
from fastapi import APIRouter, Request, Depends, HTTPException, Response

import app.db.crud as crud
from app.settings import templates, WEBROOT as SETTING_WEBROOT
from app.dependencies import get_db
from app.core.global_config import GlobalConfig
from app.core.singletons import GlobalMemcachedClient

from .auth import auth_user as _auth_user, login as _login, logout as _logout


router = APIRouter()


@router.get("/")
async def admin_panel(request: Request, db: Database = Depends(get_db)):
    cfg = GlobalConfig(db, GlobalMemcachedClient.get())
    current_user = await _auth_user(request)
    if current_user is None:
        superuser = await crud.load_superuser(db, mute_errors=True)
        if superuser:
            current_step = 0  # login form
        else:
            current_step = 1  # create superuser form
    else:
        current_step = 2  # configure Webroot & SSL

    # variables
    env = {
        'webroot': SETTING_WEBROOT
    }
    full_base_url = str(request.base_url)
    if full_base_url.endswith('/'):
        full_base_url = full_base_url[:-1]
    settings = {
        'webroot': await cfg.get_webroot(),
        'full_base_url': full_base_url
    }

    context = {
        'github': 'https://github.com/Sirius-social/didcomm',
        'issues': 'https://github.com/Sirius-social/didcomm/issues',
        'spec': 'https://identity.foundation/didcomm-messaging/spec/',
        'features': 'https://github.com/Sirius-social/didcomm#features',
        'download': 'https://hub.docker.com/r/socialsirius/didcomm',
        'base_url': '/admin',
        'current_user': current_user,
        'current_step': current_step,
        'env': env,
        'settings': settings
    }
    response = templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            **context
        }
    )
    return response


@router.post("/login", status_code=201)
async def login(request: Request, response: Response, db: Database = Depends(get_db)):
    js = await request.json()
    username, password = js.get('username'), js.get('password')
    user = await crud.load_user(db, username, mute_errors=True)
    if user:
        success = crud.check_password(user, password)
        if success:
            await _login(response, user)
        else:
            raise HTTPException(status_code=400, detail=f'Password incorrect')
    else:
        raise HTTPException(status_code=400, detail=f'Not found user with username: "{username}"')


@router.post("/create_user", status_code=201)
async def create_user(request: Request, response: Response, db: Database = Depends(get_db)):
    js = await request.json()
    username, password1, password2 = js.get('username'), js.get('password1'), js.get('password2')
    if not username:
        raise HTTPException(status_code=400, detail='Username must be filled')
    if len(username) < 4:
        raise HTTPException(status_code=400, detail='Username length must not be less than 4 symbols')
    if len(password1) < 6:
        raise HTTPException(status_code=400, detail='Password length must not be less than 6 symbols')
    if password1 != password2:
        raise HTTPException(status_code=400, detail='Passwords are not equal')
    user = await crud.load_user(db, username, mute_errors=True)
    if user:
        raise HTTPException(status_code=400, detail=f'User with username "{username}" already exists')
    else:
        user = await crud.create_user(db, username, password1)
        await login(response, user)
