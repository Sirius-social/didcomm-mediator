import aiomemcached

from app.settings import MEMCACHED as MEMCACHED_SERVER


class GlobalMemcachedClient:

    __instance = None
    MAX_POOL_SIZE = 100

    def __init__(self):
        if self.__instance:
            raise RuntimeError('GlobalMemcachedClient is singleton')
        else:
            self.memcached = aiomemcached.Client(host=MEMCACHED_SERVER, pool_maxsize=self.MAX_POOL_SIZE)

    @classmethod
    def get(cls) -> aiomemcached.Client:
        if not cls.__instance:
            cls.__instance = GlobalMemcachedClient()
        return cls.__instance.memcached
