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
