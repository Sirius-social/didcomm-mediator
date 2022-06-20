import base64
import asyncio
import threading

import aioredis
from uhashring import HashRing

from app.settings import REDIS as REDIS_SERVERS


class Bus:

    __thread_local = threading.local()
    __ctx_sub_key = 'aiobus.subscribers'
    MAX_SIZE = 1000

    def __init__(self):
        self.__queue = asyncio.Queue(maxsize=1)

    async def publish(self, topic: str, msg: bytes) -> int:
        typ, payload = 'application/base64', base64.b64encode(msg).decode('ascii')
        packet = {
            'type': typ,
            'payload': payload
        }
        url = self.get_topic_url(topic)
        redis = aioredis.Redis(pool_or_conn=await self.get_conn_pool(url))
        count = await redis.publish_json(topic, packet)
        return count

    async def listen(self, *topics: str):
        subscriptions = {}
        for topic in topics:
            url = self.get_topic_url(topic)
            channels = subscriptions.get(url, [])
            channels.append(topic)
            subscriptions[url] = channels
        instances = []
        redis_conns = []
        for url, channels in subscriptions.items():
            redis = await aioredis.create_redis(url)
            redis_conns.append(redis)
            readers = await redis.subscribe(*channels)
            instances.extend(readers)
        tasks = [asyncio.create_task(self.async_reader(sub)) for sub in instances]
        try:
            while True:
                msg = await self.__queue.get()
                yield msg
        finally:
            for tsk in tasks:
                tsk.cancel()
            for redis in redis_conns:
                redis.close()

    async def get_conn_pool(self, url: str) -> aioredis.ConnectionsPool:
        cur_loop_id = id(asyncio.get_event_loop())
        try:
            pools = self.__thread_local.pools
        except AttributeError:
            pools = {}
            self.__thread_local.pools = pools
        key = f'{cur_loop_id}:{url}'
        if key in pools:
            pool = pools[key]
        else:
            pool = await aioredis.create_redis_pool(url, maxsize=self.MAX_SIZE)
            self.__thread_local.pools[key] = pool
        return pool

    @staticmethod
    def get_topic_url(topic: str) -> str:
        ring = HashRing(nodes=REDIS_SERVERS, hash_fn='ketama')
        redis_server = ring.get_node(topic)
        url = f'redis://{redis_server}'
        return url

    async def async_reader(self, sub: aioredis.Channel):
        while sub.is_active:
            packet = await sub.get_json()
            if packet['type'] == 'application/base64':
                value = base64.b64decode(packet['payload'].encode('ascii'))
                await self.__queue.put(value)
