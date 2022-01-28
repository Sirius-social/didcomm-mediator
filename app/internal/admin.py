import asyncio
import logging
import re
import json
import uuid
import datetime

import sirius_sdk
from databases import Database
from fastapi import APIRouter, Request, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse

import asyncpg
import app.db.crud as crud
from app.settings import templates, WEBROOT as SETTING_WEBROOT, URL_STATIC, \
    CERT_FILE as SETTING_CERT_FILE, CERT_KEY_FILE as SETTING_CERT_KEY_FILE, ACME_DIR as SETTING_ACME_DIR, \
    FIREBASE_API_KEY as SETTING_FIREBASE_API_KEY, FIREBASE_SENDER_ID as SETTING_FIREBASE_SENDER_ID
from app.dependencies import get_db
from app.utils import async_build_invitation, run_in_thread
from app.core.redis import choice_server_address, AsyncRedisChannel
from app.core.emails import check_server as emails_check_server
from app.core.repo import Repo
from app.core.management import register_acme, issue_cert, reload as _mng_reload, load_cert_metadata as _mng_load_cert_metadata
from app.core.global_config import GlobalConfig
from app.core.singletons import GlobalMemcachedClient
from app.routers.utils import create_static_connection as _create_static_connection, validate_verkey as _validate_verkey

from .helpers import check_redis, check_services
from .auth import auth_user as _auth_user, login as _login, logout as _logout, SESSION_COOKIE_KEY


router = APIRouter()


BASE_URL = '/admin'
CFG_ACME_EMAIL = 'acme.email'
CFG_ACME_EMAIL_SHARE = 'acme.email.share'
PAGE_SIZE = 20
STATIC_CFG = {
    'styles': URL_STATIC + '/admin/css/styles.css',
    'vue': URL_STATIC + '/vue.min.js',
    'axios': URL_STATIC + '/axios.min.js',
    'jquery': URL_STATIC + '/jquery-3.6.0.min.js'
}


async def check_is_logged(request: Request):
    current_user = await _auth_user(request)
    if current_user is None:
        raise HTTPException(status_code=401, detail=f'Unauthorized')


@router.get("/")
async def admin_panel(request: Request, db: Database = Depends(get_db)):
    try:
        cfg = GlobalConfig(db, GlobalMemcachedClient.get())
        current_user = await _auth_user(request)
        session_id = request.cookies.get(SESSION_COOKIE_KEY)
        app_is_configured = await cfg.get_app_is_configured()

        logging.debug(f'app_is_configured: {app_is_configured}')
        logging.debug(f'current_user: {repr(current_user)}')

        if current_user is None:
            superuser = await crud.load_superuser(db, mute_errors=True)
            logging.debug('Superuser instance: ')
            if superuser:
                current_step = 0  # login form
            else:
                current_step = 1  # create superuser form
        else:
            if app_is_configured:
                current_step = 0  # login form
            else:
                current_step = 2  # configure Webroot & SSL

        # variables
        env = {
            'webroot': SETTING_WEBROOT,
            'cert_file': SETTING_CERT_FILE or '',
            'cert_key_file': SETTING_CERT_KEY_FILE or '',
            'acme_dir': SETTING_ACME_DIR or '',
            'firebase_api_key': SETTING_FIREBASE_API_KEY or '',
            'firebase_sender_id': SETTING_FIREBASE_SENDER_ID or '',
        }
        full_base_url = str(request.base_url)
        if full_base_url.endswith('/'):
            full_base_url = full_base_url[:-1]
        if 'https' == request.headers.get('x-scheme'):
            full_base_url = full_base_url.replace('http://', 'https://')
        ws_base = full_base_url.replace('http://', 'ws://').replace('https://', 'wss://')

        ssl_option = await cfg.get_ssl_option()
        if not ssl_option and request.headers.get('x-forwarded-host'):
            ssl_option = 'external'
        acme_email = await cfg.get_any_option(CFG_ACME_EMAIL)
        acme_email_share = await cfg.get_any_option(CFG_ACME_EMAIL_SHARE)
        redis_server = await choice_server_address()
        events_stream = redis_server + '/' + uuid.uuid4().hex
        events_stream_ws = f'{ws_base}/ws/events?stream=' + events_stream
        firebase_api_key, firebase_sender_id = await cfg.get_firebase_secret()
        if firebase_api_key and len(firebase_api_key) > 32:
            firebase_api_key = firebase_api_key[:13] + ' ..... ' + firebase_api_key[-5:]
        email_settings = await cfg.get_email_credentials()
        settings = {
            'webroot': await cfg.get_webroot() or full_base_url,
            'full_base_url': full_base_url,
            'ssl_option': ssl_option or 'manual',
            'acme_email': acme_email or '',
            'acme_email_share': 'true' if acme_email_share else 'false',
            'firebase_api_key': firebase_api_key or '',
            'firebase_sender_id': firebase_sender_id or '',
            'email_option': email_settings.get('option', 'no_emails'),
            'email_credentials': email_settings.get('credentials', {})
        }
        if 'x-forwarded-proto' in request.headers:
            scheme = request.headers['x-forwarded-proto']
            if scheme == 'https':
                settings['webroot'] = settings['webroot'].replace('http://', 'https://')
                settings['full_base_url'] = settings['full_base_url'].replace('http://', 'https://')
                events_stream_ws = events_stream_ws.replace('ws://', 'wss://')

        health = {}
        if app_is_configured:
            health['redis'] = await check_redis()
            health['services'] = await check_services(db)

        context = {
            'github': 'https://github.com/Sirius-social/didcomm-mediator',
            'issues': 'https://github.com/Sirius-social/didcomm-mediator/issues',
            'spec': 'https://identity.foundation/didcomm-messaging/spec/',
            'features': 'https://github.com/Sirius-social/didcomm-mediator#features',
            'download': 'https://hub.docker.com/r/socialsirius/didcomm',
            'base_url': BASE_URL,
            'current_user': current_user,
            'current_step': current_step,
            'env': env,
            'settings': settings,
            'health': health,
            'static': STATIC_CFG,
            'events_stream': events_stream,
            'events_stream_ws': events_stream_ws,
            'app_is_configured': app_is_configured,
            'invitation': await async_build_invitation(db, session_id),
            'pairwise_search': request.query_params.get('search', '')
        }
        response = templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                **context
            }
        )
        return response
    except asyncpg.exceptions.UndefinedTableError:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                'static': STATIC_CFG,
                "message": "Database is not configured"
            }
        )


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


@router.get("/logout")
async def login(request: Request, response: Response):
    await _logout(request, response)
    return RedirectResponse(url=BASE_URL)


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
        await _login(response, user)


@router.get("/ping")
async def ping():
    return {'success': True}


@router.post("/set_webroot", status_code=200)
async def set_webroot(request: Request, db: Database = Depends(get_db)):
    await check_is_logged(request)
    js = await request.json()
    value = js.get('value')
    cfg = GlobalConfig(db, GlobalMemcachedClient.get())
    await cfg.set_webroot(value)


@router.post("/set_firebase_secret", status_code=200)
async def set_firebase_secret(request: Request, db: Database = Depends(get_db)):
    await check_is_logged(request)
    js = await request.json()
    api_key = js.get('api_key')
    sender_id = js.get('sender_id')
    skip = js.get('skip', False)
    cfg = GlobalConfig(db, GlobalMemcachedClient.get())
    if skip:
        await cfg.reset_firebase_secret()
    else:
        if not api_key:
            raise HTTPException(status_code=400, detail=f'Server key is empty')
        if not sender_id:
            raise HTTPException(status_code=400, detail=f'Sender ID key is empty')
        await cfg.set_firebase_secret(api_key, sender_id)


@router.post("/set_email_credentials", status_code=200)
async def set_email_credentials(request: Request, db: Database = Depends(get_db)):
    await check_is_logged(request)
    js = await request.json()
    option = js.get('option')
    credentials = js.get('credentials')
    if not option:
        raise HTTPException(status_code=400, detail=f'option is empty')
    if option != 'no_emails':
        if not credentials:
            raise HTTPException(status_code=400, detail=f'credentials is empty')
    cfg = GlobalConfig(db, GlobalMemcachedClient.get())
    value = {
        'option': option,
        'credentials': credentials
    }
    await cfg.set_email_credentials(value)
    if option == 'server':
        for fld in ['address', 'port', 'username', 'password', 'from_email']:
            if fld not in credentials:
                raise HTTPException(status_code=400, detail=f'Field "{fld}" must be set')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print(repr(credentials))
        fut = asyncio.ensure_future(run_in_thread(
            func=emails_check_server,
            address=credentials.get('address', ''),
            port=credentials.get('port', 465),
            username=credentials.get('username', ''),
            password=credentials.get('password', ''),
            use_ssl=credentials.get('use_ssl') is True,
            use_tls=credentials.get('use_tls') is True
        ))
        try:
            await asyncio.wait([fut], timeout=5)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f'Error while try to connect. Details: ' + str(e))
        if fut.done():
            success, err = fut.result()
            if not success:
                raise HTTPException(status_code=400, detail=err)
        else:
            raise HTTPException(status_code=400, detail=f'Connection timeout expired')
    elif option == 'sendgrid':
        for fld in ['sendgrid_from_email', 'sendgrid_api_key']:
            if fld not in credentials:
                raise HTTPException(status_code=400, detail=f'Field "{fld}" must be set')
    await cfg.set_app_is_configured(True)


@router.post("/set_app_is_configured", status_code=200)
async def set_app_is_configured(request: Request, db: Database = Depends(get_db)):
    await check_is_logged(request)
    js = await request.json()
    value = js.get('value') == 'on'
    cfg = GlobalConfig(db, GlobalMemcachedClient.get())
    await cfg.set_app_is_configured(value)


@router.post("/set_ssl_option", status_code=200)
async def set_ssl_option(request: Request, db: Database = Depends(get_db)):
    await check_is_logged(request)
    js = await request.json()
    value = js.get('value')
    stream = js.get('stream')
    cfg = GlobalConfig(db, GlobalMemcachedClient.get())
    make_issue = True
    if value == 'acme':
        email = js.get('email')
        share_email = js.get('share_email')
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.match(regex, email):
            await cfg.set_any_option(CFG_ACME_EMAIL, email)
            await cfg.set_any_option(CFG_ACME_EMAIL_SHARE, share_email)
        else:
            raise HTTPException(status_code=400, detail=f'Value "{email}" is not email')

        ch = AsyncRedisChannel(address=stream)

        async def _logger(msg: str, is_error: bool = False):
            nonlocal ch
            await ch.write({
                'msg': msg,
                'is_error': is_error
            })

        await register_acme(email, share_email, _logger)
        webroot = await cfg.get_webroot()
        if not webroot:
            raise HTTPException(status_code=400, detail=f'Webroot was not set')
        domain = webroot.replace('http://', '').replace('https://', '')
        success, _domain, _utc = await _mng_load_cert_metadata(db)
        if success:
            if domain == _domain:
                utc_now = datetime.datetime.utcnow()
                utc_timestamp = datetime.datetime.utcfromtimestamp(_utc)
                limit_delta = datetime.timedelta(weeks=2)
                utc_next_call = utc_timestamp + limit_delta
                if utc_next_call > utc_now:
                    make_issue = False
                    await _logger('You can not issue new certificate no more than every 2 weeks')

        if make_issue:
            success = await issue_cert(domain, _logger)
            if not success:
                raise HTTPException(status_code=400, detail=f'Certbot error')

    await cfg.set_ssl_option(value)
    if make_issue:
        await _mng_reload()


@router.post("/load_pairwise_collection", status_code=200)
async def load_pairwise_collection(request: Request, db: Database = Depends(get_db)):
    await check_is_logged(request)
    js = await request.json()
    search = js.get('search', '')
    page = js.get('page', 1)
    #
    filters = {}
    if search:
        filters['their_label'] = search
    #
    collection_ = await crud.load_pairwises(db, filters=filters)
    collection = []
    for p in collection_:
        metadata = p['metadata'] or {}
        if not p['their_label']:
            p['their_label'] = metadata.get('their', {}).get('label', '')
        their_did_doc = metadata.get('their', {}).get('did_doc', {})
        if their_did_doc:
            p['metadata'] = their_did_doc
        collection.append(p)
    total_count = await crud.load_pairwises_count(db, filters=filters)
    return {
        'collection': collection,
        'total': total_count
    }


@router.post("/create_static_connection", status_code=200)
async def create_static_connection(request: Request, db: Database = Depends(get_db)):
    await check_is_logged(request)
    js = await request.json()
    did = js.get('did')
    verkey = js.get('verkey')
    label = js.get('label')
    fcm_device_enabled = js.get('fcm_device_enabled', False)
    fcm_device_id = js.get('fcm_device_id')

    if fcm_device_enabled:
        if not fcm_device_id:
            raise HTTPException(status_code=400, detail=f'FCM device id is Empty')
    else:
        fcm_device_id = None
    if not did:
        raise HTTPException(status_code=400, detail=f'DID not set')
    if not verkey:
        raise HTTPException(status_code=400, detail=f'Verkey not set')
    if not _validate_verkey(verkey):
        raise HTTPException(status_code=400, detail=f'Invalid verkey "{verkey}"')
    if not label:
        raise HTTPException(status_code=400, detail=f'Label not set')
    repo = Repo(db, memcached=GlobalMemcachedClient.get())

    await _create_static_connection(repo, label=label, their_did=did, their_verkey=verkey, fcm_device_id=fcm_device_id)
