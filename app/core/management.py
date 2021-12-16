import os
import asyncio
import shutil
import uuid
import subprocess
import datetime
from typing import Optional, Union, Callable

import sirius_sdk
import OpenSSL.crypto
from jinja2 import Template
from databases import Database

import settings
from app.settings import MEMCACHED
from app.dependencies import get_db
from app.db.database import database
from app.db.models import pairwises
from app.core.redis import AsyncRedisChannel
from app.db.crud import reset_global_settings as _reset_global_settings, reset_accounts as _reset_accounts, \
    create_user as _create_user, restore_path as _restore_path, dump_path as _dump_path, load_backup as _load_backup
from app.core.global_config import GlobalConfig
from app.core.singletons import GlobalMemcachedClient


ACME_DESCRIPTION = 'acme.registration'
ACME_SSL_CERT = 'acme.cert'
ACME_SSL_CERT_KEY = 'acme.cert_key'
ACME_CERT_PATH = '/tmp/cert.pem'
ACME_CERT_KEY_PATH = '/tmp/privkey.pem'
BROADCAST_CHANNEL = 'broadcast'


def run_sync(*coros):
    for coro in coros:
        asyncio.get_event_loop().run_until_complete(coro)


def ensure_database_connected():
    async def _routine():
        if not database.is_connected:
            await database.connect()
    run_sync(_routine())


def clear_memcached():
    if ':' in MEMCACHED:
        parts = MEMCACHED.split(':')
        addr, port = MEMCACHED[0], int(MEMCACHED[1])
    else:
        addr, port = MEMCACHED, 11211
    os.system(f"(echo 'flush_all' | netcat {addr} {port}) &")


async def reload():
    print('============ RELOAD ============')
    webroot = await _get_webroot()
    print(f'Webroot: {webroot}')
    ssl_option = await _get_ssl_option()
    print(f'SSL Option: {ssl_option}')
    if ssl_option == 'acme':
        ok, cert, privkey = await load_acme()
        if ok:
            if settings.ACME_DIR:
                _setup_nginx(cert, privkey, webroot or 'https', only_https=True, root_dir=settings.ACME_DIR)
            else:
                print('Warning: ACME_DIR is not set')
    elif ssl_option == 'manual':
        if settings.CERT_FILE and settings.CERT_KEY_FILE:
            _setup_nginx(settings.CERT_FILE,  settings.CERT_KEY_FILE, webroot or 'https', only_https=True)
    elif ssl_option == 'external':
        _setup_nginx(None, None, webroot or 'https', only_https=False)
    os.system("service nginx reload")
    print('================================')


def reset():
    async def _routine():
        await _reset_global_settings(database)
        await _reset_accounts(database)
    clear_memcached()
    run_sync(_routine())


def reset_accounts():
    clear_memcached()
    run_sync(_reset_accounts(database))


def create_superuser():
    username = input('Enter superuser username: ')
    while True:
        password1 = input('Type password: ')
        password2 = input('Retype password: ')
        if password1 != password2:
            print('Passwords are not equal, repeat again')
        else:
            break
    reset_accounts()
    run_sync(_create_user(database, username, password1))


def check():
    if settings.SEED is None:
        raise RuntimeError('SEED environment variable is not set !')
    sirius_sdk.encryption.validate_seed(settings.SEED)
    if (settings.CERT_FILE and not settings.CERT_KEY_FILE) or (not settings.CERT_FILE and settings.CERT_KEY_FILE):
        raise RuntimeError('You should set env variables CERT_FILE and CERT_KEY_FILE both !')
    if settings.CERT_FILE:
        if not os.path.isfile(settings.CERT_FILE):
            raise RuntimeError('Cert file "%s" does not exists' % settings.CERT_FILE)
    if settings.CERT_KEY_FILE:
        if not os.path.isfile(settings.CERT_KEY_FILE):
            raise RuntimeError('Cert file "%s" does not exists' % settings.CERT_KEY_FILE)
    if settings.ACME_DIR:
        if not os.path.isdir(settings.ACME_DIR):
            raise RuntimeError(f'Directory "{settings.ACME_DIR}" does not exists')
        # check id dir is writable
        path = os.path.join(settings.ACME_DIR, uuid.uuid4().hex)
        try:
            open(path, 'w+')
        except OSError:
            raise RuntimeError(f'Directory "{settings.ACME_DIR}" has read-only flags')
        os.remove(path)
        acme_dir = os.path.join(settings.ACME_DIR, '.well-known')
        if not os.path.exists(acme_dir):
            os.makedirs(acme_dir, 777)

    if settings.CERT_FILE and settings.CERT_KEY_FILE:
        _validate_certs(settings.CERT_FILE, settings.CERT_KEY_FILE)
        _setup_nginx(settings.CERT_FILE, settings.CERT_KEY_FILE, 'https', only_https=True)
    else:
        cert_file_path = None
        privkey_file_path = None
        if settings.ACME_DIR:
            root_dir = settings.ACME_DIR
            only_https = True
            cert_file_path = ACME_CERT_PATH if os.path.isfile(ACME_CERT_PATH) else None
            if cert_file_path:
                privkey_file_path = ACME_CERT_KEY_PATH if os.path.isfile(ACME_CERT_KEY_PATH) else None
        else:
            root_dir = None
            only_https = False
        _setup_nginx(cert_file_path, privkey_file_path, 'https', only_https=only_https, root_dir=root_dir)
    print('')
    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    print('Check OK')
    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')


async def liveness_check():
    """Checks if the application can be running."""
    # Check database
    conn = await get_db()
    if not conn.is_connected:
        raise RuntimeError('Database is not reachable')
    # Check Memcached
    cache = GlobalMemcachedClient.get()
    check_key = 'liveness_check_' + uuid.uuid4().hex
    random_value = uuid.uuid4().hex.encode()
    await cache.set(check_key.encode(), random_value, exptime=3)
    actual_value, _ = await cache.get(check_key.encode())
    if actual_value != random_value:
        raise RuntimeError('Memcached service unavailable')
    # Check Redis
    error_addrs = []
    for redis_addr in settings.REDIS:
        url = f'redis://{redis_addr}'
        ok = await AsyncRedisChannel.check_address(url)
        if not ok:
            error_addrs.append(url)
    print(repr(error_addrs))
    if error_addrs:
        raise RuntimeError('Redis addresses are unreachable: [%s]' % ','.join(error_addrs))


def generate_seed() -> str:
    value_b = sirius_sdk.encryption.random_seed()
    value = sirius_sdk.encryption.bytes_to_b58(value_b)
    return value


async def load_acme() -> (bool, Optional[str], Optional[str]):
    """

    :return: success, cert_path, privkey_path
    """
    db = Database(settings.SQLALCHEMY_DATABASE_URL)
    await db.connect()
    try:
        print('Try to load Lets Encrypt account dumps and keys')
        ok, path, ctx = await _restore_path(db, ACME_DESCRIPTION)
        if ok:
            print(f'Restored dir {path}')
        else:
            print('Not found dumps...')
        if ok:
            print('Try to load ACME cert and privkey files')
            base_dir = '/tmp'
            ok1, restored_cert_path, ctx1 = await _restore_path(db, ACME_SSL_CERT, base_dir=base_dir)
            ok2, restored_cert_key_path, ctx2 = await _restore_path(db, ACME_SSL_CERT_KEY, base_dir=base_dir)
            if ok1 and ok2:
                shutil.copy(restored_cert_path, ACME_CERT_PATH)
                shutil.copy(restored_cert_key_path, ACME_CERT_KEY_PATH)
                return True, ACME_CERT_PATH, ACME_CERT_KEY_PATH
            else:
                print('Not found cert and privkey files in backups')
                return False, None, None
        else:
            return False, None, None
    finally:
        await db.disconnect()


async def register_acme(email: str, share: bool, logger: Callable = None):

    async def empty_logger(*args, **kwargs):
        pass

    if logger:
        assert asyncio.iscoroutinefunction(logger), 'expected logger is coroutine'
        logger = asyncio.coroutine(logger)
    else:
        logger = empty_logger

    async def call_logger(msg: Union[str, bytes], *args, **kwargs):
        if type(msg) is bytes:
            msg = msg.decode()
        for line in msg.split('\n'):
            await logger(line, *args, **kwargs)

    db = Database(settings.SQLALCHEMY_DATABASE_URL)
    await db.connect()
    try:
        await logger(f"Register email {email} in Let's Encrypt service")
        ok, dump, ctx = await _load_backup(db, ACME_DESCRIPTION)
        if ok:
            old_email = ctx.get('email')
            if old_email == email:
                await logger(f'Email {email} already registered in Lets Encrypt. Finish.')
                if not os.path.isdir('/etc/letsencrypt/accounts'):
                    await logger(f'restore certbot account context')
                    await _restore_path(db, ACME_DESCRIPTION)
                return
        ctx = {'email': email, 'share': share}
        if os.path.isdir('/etc/letsencrypt/accounts'):
            shutil.rmtree('/etc/letsencrypt/accounts')
        cmd = ["certbot", "register", "--agree-tos", "--non-interactive", "-m", email]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, err = process.communicate()
        exit_code = process.wait()
        if output:
            await call_logger(output)
        if err:
            await call_logger(err, True)
        if exit_code == 0:
            await _dump_path(db, ACME_DESCRIPTION, '/etc/letsencrypt/accounts', ctx)
        else:
            raise RuntimeError('Error while register email')
    finally:
        await db.disconnect()


async def load_cert_metadata(db: Database) -> (bool, Optional[str], Optional[int]):
    """
    :return: success, domain, utc
    """
    ok, binary, ctx = await _load_backup(db, ACME_SSL_CERT)
    if ok:
        domain = ctx.get('domain')
        utc = ctx.get('utc')
        if domain and utc:
            return True, domain, utc
        else:
            return False, None, None
    else:
        return False, None, None


async def issue_cert(domain: str, logger: Callable = None) -> bool:

    async def empty_logger(*args, **kwargs):
        pass

    if logger:
        assert asyncio.iscoroutinefunction(logger), 'expected logger is coroutine'
        logger = asyncio.coroutine(logger)
    else:
        logger = empty_logger

    async def call_logger(msg: Union[str, bytes], *args, **kwargs):
        if type(msg) is bytes:
            msg = msg.decode()
        for line in msg.split('\n'):
            await logger(line, *args, **kwargs)

    db = Database(settings.SQLALCHEMY_DATABASE_URL)
    await db.connect()
    try:
        await logger(f"Issue cert for domain {domain} in Let's Encrypt service")
        if not os.path.isdir('/etc/letsencrypt/accounts'):
            await logger('You should register your email at First!', True)
            return False
        cmd = ["certbot", "certonly", "--dry-run", "-d", domain]
        await logger(f"Run certbot: %s" % ' '.join(cmd))
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, err = process.communicate()
        exit_code = process.wait()
        if output:
            await call_logger(output)
        if err:
            await call_logger(err, True)
        if exit_code == 0:
            cert_file = f'/etc/letsencrypt/live/{domain}/fullchain.pem'
            cert_key_file = f'/etc/letsencrypt/live/{domain}/privkey.pem'
            utc = datetime.datetime.utcnow()
            await _dump_path(db, ACME_SSL_CERT, cert_file, {'domain': domain, 'utc': utc})
            await _dump_path(db, ACME_SSL_CERT_KEY, cert_key_file, {'domain': domain, 'utc': utc})
            return True
        else:
            await logger('Error while issuing certificate!', True)
            return False
    finally:
        await db.disconnect()


async def broadcast(event: str):
    marker = uuid.uuid4().hex
    for address in settings.REDIS:
        address = 'redis://' + address + '/' + BROADCAST_CHANNEL
        ch = AsyncRedisChannel(address=address)
        await ch.write({
            'event': event,
            'marker': marker
        })


async def listen_broadcast():
    markers = {}

    async def _listen_channel(addr: str):
        nonlocal markers
        ch = AsyncRedisChannel(address=addr)
        print('Listen broadcasts on address: ' + addr)
        while True:
            ok, data = await ch.read(timeout=None)
            if ok:
                event = data.get('event')
                marker = data.get('marker')
                if event in markers and marker == markers[event]:
                    continue
                else:
                    print(f'Received event: "{event}" with marker: "{marker}"')
                    if event == 'reload':
                        await reload()
                    markers[event] = marker
            else:
                return

    listeners = []
    for address in settings.REDIS:
        address = 'redis://' + address + '/' + BROADCAST_CHANNEL
        fut = asyncio.ensure_future(_listen_channel(address))
        listeners.append(fut)
    await asyncio.wait(listeners, return_when=asyncio.ALL_COMPLETED)


async def create_debug_pairwise_collection():
    db = Database(settings.SQLALCHEMY_DATABASE_URL)
    await db.connect()
    try:
        sql = pairwises.delete()
        await db.execute(query=sql)
        for n in range(100):
            p2p = {
                'their_did': f'their_did[{n}]',
                'their_verkey': f'their_verkey[{n}]',
                'my_did': f'my_did[{n}]',
                'my_verkey': f'my_verkey[{n}]',
                'metadata': {
                    'key1': 5,
                    'key2': 'value'
                },
                'their_label': f'label [{n}]'
            }
            sql = pairwises.insert()
            await db.execute(query=sql, values=p2p)
    finally:
        await db.disconnect()


def _validate_certs(cert_file: str, cert_key_file: str):
    with open(cert_file, 'rb') as f:
        content = f.read()
        cert_obj = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, content)
    with open(cert_key_file, 'rb') as f:
        content = f.read()
        private_key_obj = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, content)
    context = OpenSSL.SSL.Context(OpenSSL.SSL.TLSv1_METHOD)
    context.use_privatekey(private_key_obj)
    context.use_certificate(cert_obj)
    context.check_privatekey()


def _setup_nginx(cert_file: Optional[str], cert_key_file: Optional[str], webroot: Optional[str], only_https: bool, root_dir: str = None):
    proxy_tmp = Template(NGINX_PROXY_JINJA_TEMPLATE)
    render_proxy = proxy_tmp.render(asgi_port=settings.PORT)
    cfg_tmp = Template(NGINX_CFG_JINJA_TEMPLATE.replace('<proxy>', render_proxy))
    if root_dir is None:
        root_dir = '/var/www/html'
    render_cfg = cfg_tmp.render(
        root_dir=root_dir, cert_file=cert_file, cert_key=cert_key_file, webroot=webroot, only_https=only_https
    )
    with open('/etc/nginx/sites-available/default', 'w') as f:
        f.truncate()
        f.write(render_cfg)
    cmd = ["nginx", "-t"]
    exit_code = subprocess.call(cmd)
    if exit_code != 0:
        raise RuntimeError('Setup Nginx error!')


async def _get_webroot() -> Optional[str]:
    # allocate db conn
    db = Database(settings.SQLALCHEMY_DATABASE_URL)
    await db.connect()
    try:
        cfg = GlobalConfig(db, GlobalMemcachedClient.get())
        value = await cfg.get_webroot()
        return value
    finally:
        await db.disconnect()


async def _get_ssl_option() -> Optional[str]:
    # allocate db conn
    db = Database(settings.SQLALCHEMY_DATABASE_URL)
    await db.connect()
    try:
        cfg = GlobalConfig(db, GlobalMemcachedClient.get())
        value = await cfg.get_ssl_option()
        return value
    finally:
        await db.disconnect()

NGINX_PROXY_JINJA_TEMPLATE = """
    location /ws {
            proxy_pass http://localhost:{{ asgi_port }};
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "Upgrade";
            
            # By default, the connection will be closed if the proxied server does not 
            # transmit any data within 60 seconds
            # proxy_read_timeout 60;
    }
    location /polling {
            proxy_set_header Host $http_host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_pass http://localhost:{{ asgi_port }};
            proxy_read_timeout 3600;
    }
    location / {
            proxy_set_header Host $http_host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_pass http://localhost:{{ asgi_port }};
    }
"""

NGINX_CFG_JINJA_TEMPLATE = """
server {
        listen 80;
        listen [::]:80;
        server_name http;
   
        location ^~ /.well-known/acme-challenge/ {
                # --- LETSENCRYPT ---
                root {{ root_dir}};
                try_files $uri $uri/ =404;
        }
        {% if only_https %}
            location / {
                return 301 https://$host$request_uri;
            }
        {% else %}
            <proxy>
        {% endif %}    
}

{% if cert_file  %}
server {
        server_name {{ webroot }};
        listen 443 ssl;
        ssl_certificate         {{ cert_file }};
        ssl_certificate_key     {{ cert_key }};
        ssl_protocols           TLSv1 TLSv1.1 TLSv1.2;
        
        <proxy>
}
{% endif %}
"""
