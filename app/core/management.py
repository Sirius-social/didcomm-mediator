import os
import asyncio

import sirius_sdk

import settings
from app.settings import MEMCACHED
from app.db.database import database
from app.db.crud import reset_global_settings as _reset_global_settings, reset_accounts as _reset_accounts, \
    create_user as _create_user


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
        raise RuntimeError('SEED environment variable is not set')
    sirius_sdk.encryption.validate_seed(settings.SEED)
    print('')
    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    print('Check OK')
    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')


def generate_seed() -> str:
    value_b = sirius_sdk.encryption.random_seed()
    value = sirius_sdk.encryption.bytes_to_b58(value_b)
    return value


NGINX_CFH_JINJA_TEMPLATE = """
server {
        listen 80;
        listen [::]:80;
        server_name http;

        index index.html;

        location ^~ /.well-known/acme-challenge/ {
                # --- LETSENCRYPT ---
                root {{ root_dir}};
                try_files $uri $uri/ =404;
        }
}


server {
        server_name {{ webroot }};
        listen 443 ssl;
        ssl_certificate         {{ cert_file }};
        ssl_certificate_key     {{ cert_key }};
        ssl_protocols           TLSv1 TLSv1.1 TLSv1.2;
        
        location /ws {
                proxy_pass http://localhost:8000;
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
                proxy_pass http://localhost:8000;
        }
}
"""
