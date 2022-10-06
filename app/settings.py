import os
import logging

import sirius_sdk
from fastapi.templating import Jinja2Templates


log_levels = {
    'CRITICAL': logging.CRITICAL,
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG
}
log_level = log_levels.get(os.getenv('LOGLEVEL', None))
if log_level:
    logging.getLogger().setLevel(log_level)
    logging.getLogger("asyncio").setLevel(log_level)


if os.getenv('ELK', None) == 'on':
    from app.elk import ElkJsonFormatter
    logger = logging.getLogger()
    logHandler = logging.StreamHandler()
    formatter = ElkJsonFormatter()
    logHandler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(logHandler)


templates = Jinja2Templates(directory="templates")

PORT = int(os.getenv('PORT'))
URL_STATIC = '/static'
ENDPOINTS_PATH_PREFIX = 'e'
ROUTER_PATH = 'endpoint'
LONG_POLLING_PATH_PREFIX = 'polling'
WS_PATH_PREFIX = 'ws'

MEMCACHED = os.environ.get('MEMCACHED')
assert MEMCACHED is not None, 'You must set MEMCACHED env variable that specify memcached server address'
if ':' in MEMCACHED:
    host, port = MEMCACHED.split(':')
    MEMCACHED = host
    MEMCACHED_PORT = int(port)
else:
    MEMCACHED_PORT = 11211

MSG_DELIVERY_SERVICES = os.environ.get('MSG_DELIVERY_SERVICES') or os.environ.get('REDIS')
assert MSG_DELIVERY_SERVICES is not None, 'You must set MSG_DELIVERY_SERVICES env variable, for example: "redis://address1,redis://address2"'
REDIS = []
for item in MSG_DELIVERY_SERVICES.split(','):
    parts = item.split('://')
    if len(parts) > 1:
        scheme, address = parts[0], parts[1]
        if scheme == 'redis':
            REDIS.append(address)
    else:
        address = item
        REDIS.append(address)


WEBROOT = os.environ.get('WEBROOT')

DEVICE_ACK_TIMEOUT = 15

# Postgres
DATABASE_HOST = os.getenv('DATABASE_HOST')
assert DATABASE_HOST is not None, 'You must set DATABASE_HOST env variable'
DATABASE_NAME = os.getenv('DATABASE_NAME')
assert DATABASE_NAME is not None, 'You must set DATABASE_NAME env variable'
DATABASE_USER = os.getenv('DATABASE_USER')
assert DATABASE_USER is not None, 'You must set DATABASE_USER env variable'
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
assert DATABASE_PASSWORD is not None, 'You must set DATABASE_PASSWORD env variable'
DATABASE_PORT = int(os.getenv('DATABASE_PORT', 5432))
TEST_DATABASE_NAME = 'test_database'

SQLALCHEMY_DATABASE_URL = \
    f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
TEST_SQLALCHEMY_DATABASE_URL = \
    f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{TEST_DATABASE_NAME}"


SEED = os.getenv('SEED')
if SEED is not None:
    sirius_sdk.encryption.validate_seed(SEED)

if SEED is None:
    KEYPAIR = None, None
    DID = None
else:
    pub, priv = sirius_sdk.encryption.create_keypair(seed=SEED.encode())
    KEYPAIR = sirius_sdk.encryption.bytes_to_b58(pub), sirius_sdk.encryption.ed25519.bytes_to_b58(priv)
    did = sirius_sdk.encryption.did_from_verkey(verkey=pub)
    DID = sirius_sdk.encryption.bytes_to_b58(did)

MEDIATOR_LABEL = os.getenv('LABEL', 'Mediator')

FIREBASE_API_KEY = os.getenv('FCM_API_KEY')
if FIREBASE_API_KEY is None:
    logging.getLogger().warning('FCM_API_KEY env var not set')
FIREBASE_SENDER_ID = os.getenv('FCM_SENDER_ID')
if FIREBASE_API_KEY and FIREBASE_SENDER_ID is None:
    assert 0, 'You must set FCM_SENDER_ID env variable'


FCM_SERVICE_TYPE = 'FCMService'
MEDIATOR_SERVICE_TYPE = 'MediatorService'


CERT_FILE = os.getenv('CERT_FILE')
CERT_KEY_FILE = os.getenv('CERT_KEY_FILE')
ACME_DIR = os.getenv('ACME_DIR')
