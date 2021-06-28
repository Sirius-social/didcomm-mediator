import os

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
