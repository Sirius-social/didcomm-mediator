#!/usr/bin/env python

import argparse

import app.core.management


CMD_RESET = 'reset'
CMD_CREATE_SUPERUSER = 'create_superuser'
CMD_CHECK = 'check'
ALL_CMD = [CMD_CREATE_SUPERUSER, CMD_CHECK, CMD_RESET]

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    'command', choices=ALL_CMD, type=str,
    help=f"reset all user and settings data. You should configure application again."
)
args = arg_parser.parse_args()


command = args.command


app.core.management.ensure_database_connected()


if command == CMD_CREATE_SUPERUSER:
    app.core.management.create_superuser()
elif command == CMD_CHECK:
    app.core.management.check()
elif command == CMD_RESET:
    app.core.management.reset()

