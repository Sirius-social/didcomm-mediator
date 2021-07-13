import os

import sirius_sdk
from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory="templates")


ENDPOINTS_PATH_PREFIX = 'e'

MEMCACHED = os.environ.get('MEMCACHED')
assert MEMCACHED is not None, 'You must set MEMCACHED env variable that specify memcached server address'

REDIS = os.environ.get('REDIS')
assert REDIS is not None, 'You must set REDIS env variable, for example: "address1,address2"'
REDIS = REDIS.split(',')

WEBROOT = os.environ.get('WEBROOT')
assert REDIS is not None, 'You must set WEBROOT env variable, for example: "https://myserver.com"'

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
assert SEED is not None, 'You must set SEED env variable'
pub, priv = sirius_sdk.encryption.create_keypair(seed=os.getenv('SEED').encode())
KEYPAIR = sirius_sdk.encryption.bytes_to_b58(pub), sirius_sdk.encryption.ed25519.bytes_to_b58(priv)
did = sirius_sdk.encryption.did_from_verkey(verkey=pub)
DID = sirius_sdk.encryption.bytes_to_b58(did)
MEDIATOR_LABEL = os.getenv('LABEL', 'Mediator')


FCM_SERVICE_TYPE = 'FCMService'
MEDIATOR_SERVICE_TYPE = 'MediatorService'

