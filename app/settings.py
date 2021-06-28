import os

import sirius_sdk
from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory="templates")


REDIS = os.environ.get('REDIS')
assert REDIS is not None, 'You must set REDIS env variable'
REDIS = REDIS.split(',')


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

SQLALCHEMY_DATABASE_URL = \
    f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"


RELAY_KEYPAIR = (None, None)
if os.getenv('SEED'):
    pub, priv = sirius_sdk.encryption.ed25519.create_keypair(seed=os.getenv('SEED').encode())
    RELAY_KEYPAIR = sirius_sdk.encryption.ed25519.bytes_to_b58(pub), sirius_sdk.encryption.ed25519.bytes_to_b58(priv)
