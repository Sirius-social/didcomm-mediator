#!/usr/bin/env python

import asyncio
import argparse
import logging

CMD_RESET = 'reset'
CMD_CREATE_SUPERUSER = 'create_superuser'
CMD_CHECK = 'check'
CMD_GENERATE_SEED = 'generate_seed'
CMD_RELOAD = 'reload'
CDM_LISTEN_FOR_CHANGES = 'listen_for_changes'
ALL_CMD = [CMD_CREATE_SUPERUSER, CMD_CHECK, CMD_RESET, CMD_GENERATE_SEED, CMD_RELOAD, CDM_LISTEN_FOR_CHANGES]

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    'command', choices=ALL_CMD, type=str,
    help=f"reset all user and settings data. You should configure application again."
)
arg_parser.add_argument('--broadcast', type=str, required=False)
args = arg_parser.parse_args()


command = args.command
broadcast = args.broadcast in ['on', 'yes']


if command == CMD_GENERATE_SEED:

    import sirius_sdk

    def _generate_seed() -> str:
        value_b = sirius_sdk.encryption.random_seed()
        value = sirius_sdk.encryption.bytes_to_b58(value_b)
        return value[:32]

    seed = _generate_seed()
    print('')
    print('=================================================================================')
    print('SEED value is: ')
    print('\t\t' + seed)
    print('place it to SEED environment variable')
    print('=================================================================================')
else:

    import app.core.management
    app.core.management.ensure_database_connected()

    if command == CMD_CREATE_SUPERUSER:
        app.core.management.create_superuser()
    elif command == CMD_CHECK:
        logging.warning('Check configuration...')
        app.core.management.check()
        logging.warning('ok')
        logging.warning('Check liveness...')
        asyncio.get_event_loop().run_until_complete(app.core.management.liveness_check())
        logging.warning('ok')
        asyncio.get_event_loop().run_until_complete(app.core.management.reload())
    elif command == CMD_RESET:
        choice = input('Clear all accounts and settings? y/n: ')
        if choice == 'y':
            print('Accepted')
            app.core.management.reset()
        else:
            print('Declined')
    elif command == CMD_RELOAD:
        asyncio.get_event_loop().run_until_complete(app.core.management.reload())
        if broadcast is True:
            asyncio.get_event_loop().run_until_complete(app.core.management.broadcast(event=CMD_RELOAD))
    elif command == CDM_LISTEN_FOR_CHANGES:
        asyncio.get_event_loop().run_until_complete(app.core.management.listen_broadcast())
