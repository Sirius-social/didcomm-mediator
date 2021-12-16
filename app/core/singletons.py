import asyncio
import aiomemcached

from expiringdict import ExpiringDict

from app.settings import MEMCACHED as MEMCACHED_SERVER, MEMCACHED_PORT


class GlobalMemcachedClient:

    __instances = {}
    MAX_POOL_SIZE = 100

    def __init__(self):
        cur_loop_id = self._get_cur_loop_id()
        if cur_loop_id in self.__instances.keys():
            raise RuntimeError('GlobalMemcachedClient is singleton')
        else:
            self.memcached = aiomemcached.Client(
                host=MEMCACHED_SERVER, port=MEMCACHED_PORT, pool_maxsize=self.MAX_POOL_SIZE
            )

    @staticmethod
    def _get_cur_loop_id() -> int:
        # Memcached Aio api is critical to current running loop
        cur_loop = asyncio.get_event_loop()
        if cur_loop:
            cur_loop_id = id(cur_loop)
        else:
            cur_loop_id = 0
        return cur_loop_id

    @classmethod
    def get(cls) -> aiomemcached.Client:
        cur_loop_id = cls._get_cur_loop_id()
        inst = cls.__instances.get(cur_loop_id)
        if not inst:
            inst = GlobalMemcachedClient()
            cls.__instances[cur_loop_id] = inst
        return inst.memcached


class GlobalRedisChannelsCache:

    __instance = None
    EXPIRE_SEC = 60
    MAX_CHANNELS = 1000

    def __init__(self):
        if self.__instance:
            raise RuntimeError('GlobalMemcachedClient is singleton')
        else:
            self.cache = ExpiringDict(max_len=self.MAX_CHANNELS, max_age_seconds=self.EXPIRE_SEC)

    @classmethod
    def get(cls) -> ExpiringDict:
        if not cls.__instance:
            cls.__instance = GlobalRedisChannelsCache()
        return cls.__instance.cache
