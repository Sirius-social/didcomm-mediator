import os

import sirius_sdk
from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory="templates")


MEMCACHED = os.environ.get('MEMCACHED')
assert MEMCACHED is not None, 'You must set MEMCACHED env variable'


WEBROOT = os.getenv('WEBROOT')
assert WEBROOT is not None, 'You must set WEBROOT env variable'
