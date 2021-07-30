import os
import asyncio
import shutil
import uuid
import subprocess
from typing import Optional, Union

import sirius_sdk
import OpenSSL.crypto
from jinja2 import Template
from databases import Database

import settings
from app.settings import MEMCACHED
from app.db.database import database
from app.db.crud import reset_global_settings as _reset_global_settings, reset_accounts as _reset_accounts, \
    create_user as _create_user, restore_path as _restore_path, dump_path as _dump_path, load_backup as _load_backup
from app.core.global_config import GlobalConfig
from app.core.singletons import GlobalMemcachedClient


ACME_DESCRIPTION = 'acme.registration'


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


def reload():
    print('============ RELOAD ============')
    asyncio.get_event_loop().run_until_complete(load_acme())
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

    if settings.CERT_FILE and settings.CERT_KEY_FILE:
        _validate_certs(settings.CERT_FILE, settings.CERT_KEY_FILE)
        _setup_nginx(settings.CERT_FILE, settings.CERT_KEY_FILE, 'https', only_https=True)
    else:
        _setup_nginx(None, None, 'https', only_https=False)
    print('')
    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    print('Check OK')
    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')


def generate_seed() -> str:
    value_b = sirius_sdk.encryption.random_seed()
    value = sirius_sdk.encryption.bytes_to_b58(value_b)
    return value


async def load_acme():
    db = Database(settings.SQLALCHEMY_DATABASE_URL)
    await db.connect()
    try:
        print('Try to load Lets Encrypt account dumps and keys')
        ok, path, ctx = await _restore_path(db, ACME_DESCRIPTION)
        if ok:
            print(f'Restored dir {path}')
        else:
            print('Not found dumps...')
    finally:
        await db.disconnect()


async def register_acme(email: str, share: bool, logger: None):

    async def empty_logger(*args, **kwargs):
        pass

    if logger:
        assert asyncio.iscoroutinefunction(logger), 'expected logger is coroutine'
        logger = asyncio.coroutine(logger)
    else:
        logger = empty_logger

    async def call_logger(msg: Union[str, bytes]):
        if type(msg) is bytes:
            msg = msg.decode()
        for line in msg.split('\n'):
            await logger(line)

    db = Database(settings.SQLALCHEMY_DATABASE_URL)
    await db.connect()
    try:
        await logger(f"Register email {email} in Let's Encrypt service")
        ok, dump, ctx = await _load_backup(db, ACME_DESCRIPTION)
        if ok:
            old_email = ctx.get('email')
            if old_email == email:
                await logger(f'Email {email} already registered in Lets Encrypt. Finish.')
                return
        ctx = {'email': email, 'share': share}
        if os.path.isdir('/etc/letsencrypt/accounts'):
            shutil.rmtree('/etc/letsencrypt/accounts')
        cmd = ["certbot", "register", "--agree-tos", "--non-interactive", "-m", email]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        output, err = process.communicate()
        exit_code = process.wait()
        await call_logger(output)
        await call_logger(err, True)
        if exit_code == 0:
            await _dump_path(db, ACME_DESCRIPTION, '/etc/letsencrypt/accounts', ctx)
        else:
            raise RuntimeError('Error while register email')
    finally:
        await db.disconnect()


def _register_email_with_certbot(email: str, share: bool, logger):
    cmd = ["certbot", "register", "--agree-tos", "--non-interactive", "-m", email]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (output, err) = process.communicate()
    print(repr(output))
    print(repr(err))
    exit_code = process.wait()
    if exit_code != 0:
        pass


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


def _setup_nginx(cert_file: Optional[str], cert_key_file: Optional[str], webroot: Optional[str], only_https: bool):
    proxy_tmp = Template(NGINX_PROXY_JINJA_TEMPLATE)
    render_proxy = proxy_tmp.render(asgi_port=settings.PORT)
    cfg_tmp = Template(NGINX_CFG_JINJA_TEMPLATE.replace('<proxy>', render_proxy))
    render_cfg = cfg_tmp.render(
        root_dir='/var/www/html', cert_file=cert_file, cert_key=cert_key_file, webroot=webroot, only_https=only_https
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
