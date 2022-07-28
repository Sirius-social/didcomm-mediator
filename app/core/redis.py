import uuid
import math
import json
import random
import asyncio
import datetime
import hashlib
import logging
from typing import Any, Optional, Dict
from contextlib import asynccontextmanager

import aioredis
import aiomemcached
from databases import Database
from expiringdict import ExpiringDict

from app.settings import REDIS as REDIS_SERVERS, MEMCACHED as MEMCACHED_SERVER
from app.db.crud import load_endpoint


class ReadWriteTimeoutError(Exception):
    pass


class RedisConnectionError(Exception):
    pass


class NoOneReachableRedisServer(Exception):
    pass


PUSH_MSG_TYPE = 'https://didcomm.org/redis/1.0/push'
ACK_MSG_TYPE = 'https://didcomm.org/redis/1.0/ack'


async def choice_server_address(unwanted: str = None) -> str:
    if unwanted:
        unwanted = unwanted.replace('redis://', '')
    items = REDIS_SERVERS[:]
    random.shuffle(items)
    if unwanted and unwanted in items:
        excluded = [i for i in items if i != unwanted]
        items = excluded + [unwanted]  # shift to tail unwanted address
    for item in items:
        addr = f'redis://{item}'
        ok = await AsyncRedisChannel.check_address(addr)
        if ok:
            return addr
    s = ','.join(REDIS_SERVERS)
    raise NoOneReachableRedisServer(f'NoOne of redis servers [{s}] is reachable')


class AsyncRedisChannel:

    TIMEOUT = 5

    def __init__(self, address: str, loop: asyncio.AbstractEventLoop = None, group_id: str = None):
        """
        param: address (str) for example 'redis://redis1/xxx'
        """

        self.__orig_address = address
        self.__name = address.split('/')[-1]
        self.__group_id = group_id
        self.__address = address.replace(f'/{self.__name}', '')
        self.__aio_redis = None
        self.__queue = asyncio.Queue()
        self.__channel = None
        self.__loop = loop or asyncio.get_event_loop()

    def __del__(self):
        if self.__aio_redis and self.__loop.is_running():
            asyncio.ensure_future(self.__terminate(), loop=self.__loop)

    @property
    def address(self) -> str:
        return self.__orig_address

    @property
    def group_id(self) -> Optional[str]:
        return self.__group_id

    @asynccontextmanager
    async def connection(self):
        if self.__aio_redis and self.__aio_redis.closed:
            create_connection = True
        elif self.__aio_redis is None:
            create_connection = True
        else:
            create_connection = False
        if create_connection:
            self.__channel = None
            try:
                self.__aio_redis = await aioredis.create_redis(self.__address, timeout=self.TIMEOUT)
            except Exception:
                raise RedisConnectionError(f'Error connection for {self.__address}')
        yield self.__aio_redis

    @asynccontextmanager
    async def channel(self):
        try:
            async with self.connection() as conn:
                if self.__channel is None:
                    try:
                        res = await conn.subscribe(self.__name)
                    except Exception:
                        raise RedisConnectionError(f'Error subscribe to {self.__name}')
                    self.__channel = res[0]
                yield self.__channel
        except RedisConnectionError:
            await self.__terminate()
            raise

    async def read(self, timeout) -> (bool, Any):
        async with self.channel():
            try:
                while True:
                    await asyncio.wait_for(self.__async_reader(), timeout=timeout)
                    packet = self.__queue.get_nowait()
                    if packet['kind'] == 'data':
                        break
                    elif packet['kind'] == 'close':
                        await self.__terminate()
                        return False, None
            except asyncio.TimeoutError:
                raise ReadWriteTimeoutError
            else:
                data = packet['body']
                return True, data

    async def write(self, data) -> bool:
        """Send data to recipients
        Return: True if almost one recipient received packet
        """
        async with self.connection() as conn:
            packet = dict(kind='data', body=data)
            try:
                counter = await conn.publish_json(self.__name, packet)
            except aioredis.errors.RedisError:
                raise RedisConnectionError()
            return counter > 0

    async def close(self):
        async with self.connection() as conn:
            packet = dict(kind='close', body=None)
            try:
                await conn.publish_json(self.__name, packet)
            except aioredis.errors.RedisError:
                raise RedisConnectionError()

    @staticmethod
    async def check_address(address: str) -> bool:
        """
        Example: address = redis://redis
        """
        try:
            conn = await aioredis.create_redis(address, timeout=3)
            ok = await conn.ping()
            conn.close()
            return ok == b'PONG'
        except Exception as e:
            return False

    async def __async_reader(self):
        try:
            await self.__channel.wait_message()
            msg = await self.__channel.get_json()
        except aioredis.errors.RedisError:
            raise RedisConnectionError()
        self.__queue.put_nowait(msg)

    async def __terminate(self):
        if self.__aio_redis:
            self.__aio_redis.close()
            self.__channel = None
            self.__aio_redis = None


class AsyncRedisGroup:

    TIMEOUT = 5

    def __init__(self, address: str, loop: asyncio.AbstractEventLoop = None, group_id: str = None, read_count: int = 1):
        """
        param: address (str) for example 'redis://redis1/xxx'
        """

        self.__orig_address = address
        self.__name = address.split('/')[-1]
        self.__group_id = group_id or '*'
        self.__address = address.replace(f'/{self.__name}', '')
        self.__aio_redis = None
        self.__mkstream = False
        self.__self_id = str(id(self))
        self.__loop = loop or asyncio.get_event_loop()
        self.__read_count = read_count or 1
        self.__queue = asyncio.Queue()

    def __del__(self):
        if self.__aio_redis and self.__loop.is_running():
            asyncio.ensure_future(self.__terminate(), loop=self.__loop)

    @property
    def address(self) -> str:
        return self.__orig_address

    @property
    def group_id(self) -> Optional[str]:
        return self.__group_id

    @property
    def self_id(self) -> str:
        return self.__self_id

    @asynccontextmanager
    async def connection(self):
        if self.__aio_redis and self.__aio_redis.closed:
            create_connection = True
        elif self.__aio_redis is None:
            create_connection = True
        else:
            create_connection = False
        if create_connection:
            try:
                self.__aio_redis = await aioredis.create_redis(self.__address, timeout=self.TIMEOUT)
            except Exception as e:
                raise RedisConnectionError(f'Error connection for {self.__address}')
        yield self.__aio_redis

    async def read(self, timeout) -> (bool, Any):
        logging.debug(f'.... AsyncRedisGroup.read(timeout: "{timeout}")')
        try:
            if not self.__queue.empty():
                data = self.__queue.get_nowait()
                return True, data
            else:
                logging.debug(f'.... #1')
                async with self.connection() as redis:
                    try:
                        logging.debug(f'.... #2')
                        if timeout is None:
                            await asyncio.wait_for(self.__async_reader_infinite(redis), timeout=None)
                        else:
                            await asyncio.wait_for(self.__async_reader(redis, timeout), timeout=timeout)
                        if self.__queue.empty():
                            raise ReadWriteTimeoutError
                        else:
                            data = self.__queue.get_nowait()
                        logging.debug(f'.... #3')
                        return True, data
                    except asyncio.TimeoutError:
                        raise ReadWriteTimeoutError
            return False, None
        except Exception as e:
            logging.exception(f'.... Exception in AsyncRedisGroup.read address: {self.__address}')
            raise

    async def write(self, data) -> bool:
        """Send data to recipients
        Return: True if almost one recipient received packet
        """
        async with self.connection() as redis:
            try:
                payload = {b'payload': json.dumps(data).encode()}
                try:
                    logging.debug(f'.... start to redis.xadd stream: {self.__name}')
                    msg_id = await redis.xadd(stream=self.__name, fields=payload)
                    logging.debug(f'.... stop to redis.xadd msg_id: {msg_id}')
                except Exception as e:
                    logging.exception(f'Exception in write operation for {self.__address}')
                    raise
            except aioredis.errors.RedisError:
                raise RedisConnectionError()
            return True

    async def close(self, later: bool = False):
        if self.__aio_redis is not None:
            try:
                try:
                    redis = self.__aio_redis
                    if self.group_id:
                        try:
                            coro = redis.xgroup_delconsumer(
                                stream=self.__name,
                                group_name=self.group_id,
                                consumer_name=self.__self_id
                            )
                            if later:
                                if self.__loop and self.__loop.is_running():
                                    asyncio.ensure_future(coro, loop=self.__loop)
                            else:
                                num = await coro
                                logging.debug(f'xgroup_delconsumer returned: {num}')
                        except Exception as e:
                            logging.exception('Error in xgroup_delconsumer')
                    self.__aio_redis.close()
                finally:
                    self.__aio_redis = None
            except aioredis.errors.RedisError as e:
                logging.exception(f'Exception on close: {self.address}')

    @staticmethod
    async def check_address(address: str) -> bool:
        """
        Example: address = redis://redis
        """
        try:
            conn = await aioredis.create_redis(address, timeout=3)
            ok = await conn.ping()
            conn.close()
            return ok == b'PONG'
        except Exception as e:
            return False

    async def info_consumers(self) -> Any:
        async with self.connection() as redis:
            info = await redis.xinfo_consumers(stream=self.__name, group_name=self.__group_id)
            return info

    async def __async_reader(self, redis: aioredis.Redis, read_timeout: float = None):
        latest_ids = ['>']
        if self.__group_id and not self.__mkstream:
            self.__mkstream = await self.__ensure_group_exists(redis)
        try:
            logging.debug(f'.... start to redis.xread_group group_name: {self.__group_id} consumer_name: {self.__self_id} streams: {[self.__name]}')
            read_timeout_milliseconds = math.floor(read_timeout * 1000) if read_timeout is not None else 0
            messages = await redis.xread_group(
                group_name=self.__group_id,
                consumer_name=self.__self_id,
                streams=[self.__name],
                latest_ids=latest_ids,
                count=self.__read_count,
                timeout=read_timeout_milliseconds
            )
            logging.debug(f'.... stop to redis.xread_group  len(messages) = {len(messages)} group_name: {self.__group_id} consumer_name: {self.__self_id} streams: {[self.__name]}')
            for partition, msg_id, fields in messages:
                payload = fields.get(b'payload')
                if payload:
                    msg = json.loads(payload.decode())
                    await self.__queue.put(msg)
            if len(messages) > 0:
                return
        except Exception as e:
            logging.exception(f'Exception [{self.__address}]')
            if isinstance(e, aioredis.errors.RedisError):
                raise RedisConnectionError()
            if isinstance(e, asyncio.CancelledError):
                return
            else:
                raise

    async def __async_reader_infinite(self, redis: aioredis.Redis):
        read_timeout_sec = 1
        while self.__queue.empty():
            await self.__async_reader(redis, read_timeout_sec)

    async def __terminate(self):
        if self.__aio_redis:
            self.__aio_redis.close()
            self.__aio_redis = None

    async def __ensure_group_exists(self, redis: aioredis.Redis) -> bool:
        if redis:
            try:
                success = await redis.xgroup_create(stream=self.__name, group_name=self.__group_id, mkstream=True)
                if not success:
                    return False
            except Exception as e:
                logging.exception(f'Exception [{self.__address}]')
                if isinstance(e, aioredis.errors.BusyGroupError):
                    pass
                else:
                    return False
            return True
        else:
            return False


class RedisPush:

    EXPIRE_SEC = 60
    MAX_CHANNELS = 1000
    REVERSE_FORWARD_CH_EQUAL = True

    def __init__(self, db: Database, memcached: aiomemcached.Client = None, channels_cache: ExpiringDict = None):
        self.__db = db
        self.__endpoints_cache = memcached or aiomemcached.Client(host=MEMCACHED_SERVER, pool_maxsize=self.MAX_CHANNELS)
        self.__channels_cache = channels_cache or ExpiringDict(max_len=self.MAX_CHANNELS, max_age_seconds=self.EXPIRE_SEC)

    async def push(self, endpoint_id: str, message: dict, ttl: int) -> bool:
        expire_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl)
        for cnt in range(2):
            try:
                success = await self.__push_internal(endpoint_id, message, expire_at)
                return success
            except RedisConnectionError:
                raise
            except ReadWriteTimeoutError:
                return False

    async def __push_internal(self, endpoint_id: str, message, expire_at: datetime) -> bool:
        for ignore_cache in [False, True]:
            forward_channel, reverse_channel = await self.__get_channel(endpoint_id, ignore_cache)
            if forward_channel and reverse_channel:
                logging.debug(f'!!! Forward channel: {forward_channel.address}')
                logging.debug(f'!!! Reverse channel: {reverse_channel.address}')
            if forward_channel:
                request = {
                    '@id': uuid.uuid4().hex,
                    '@type': PUSH_MSG_TYPE,
                    'reverse_channel': reverse_channel.address,
                    'expire_at': expire_at.utcnow().timestamp(),
                    'message': message
                }
                async with self.__clean_on_disconnect(endpoint_id, forward_channel):
                    # Bootstrap reverse-channel
                    async with reverse_channel.channel():
                        success = await forward_channel.write(request)
                if success:
                    # Wait for answer
                    while datetime.datetime.utcnow() <= expire_at:
                        delta = expire_at - datetime.datetime.utcnow()
                        async with self.__clean_on_disconnect(endpoint_id, forward_channel):
                            ok, response = await reverse_channel.read(delta.total_seconds())
                        if ok:
                            if response.get('@type') == ACK_MSG_TYPE and response['@id'] == request['@id']:
                                return response['status'] is True
                            else:
                                logging.warning(f"Expected @id={request['@id']}, Received @id={response['@id']}")
                        else:
                            return False
                    return False
                else:
                    return False
        return False

    async def __get_channel(self, endpoint_id: str, ignore_cache: bool = False) -> (Optional[AsyncRedisGroup], Optional[AsyncRedisChannel]):
        address = await self.__get_session_channel_address(endpoint_id, ignore_cache)
        if address:
            cached = self.__channels_cache.get(address)
            if cached is None:
                forward_ch = AsyncRedisGroup(address)
                if self.REVERSE_FORWARD_CH_EQUAL:
                    reverse_ch = AsyncRedisChannel(address=address)
                else:
                    reverse_name = hashlib.sha256(address.encode('utf-8')).hexdigest()
                    random_redis_addr = await self.__choice_server_address()
                    reverse_addr = f'{random_redis_addr}/{reverse_name}'
                    reverse_ch = AsyncRedisChannel(reverse_addr)
                self.__channels_cache[address] = (forward_ch, reverse_ch)
                return forward_ch, reverse_ch
            else:
                forward_ch, reverse_ch = cached
                return forward_ch, reverse_ch
        else:
            return None, None

    async def __get_session_channel_address(self, endpoint_id: str, ignore_cache: bool = False) -> Optional[str]:
        addr, _ = await self.__endpoints_cache.get(endpoint_id.encode())
        address = addr.decode() if addr else None
        if address and ignore_cache:
            await self.__endpoints_cache.delete(endpoint_id.encode())
        if not address or ignore_cache:
            endpoint = await load_endpoint(db=self.__db, uid=endpoint_id)
            if endpoint:
                address = endpoint['redis_pub_sub']
                if address:
                    await self.__endpoints_cache.set(endpoint_id.encode(), address.encode())
                return address
            else:
                return None

    @asynccontextmanager
    async def __clean_on_disconnect(self, endpoint_id: str, channel: AsyncRedisChannel):
        try:
            yield
        except RedisConnectionError:
            await self.__endpoints_cache.delete(endpoint_id.encode())
            if channel.address in self.__channels_cache:
                del self.__channels_cache[channel.address]
            raise

    @staticmethod
    async def __choice_server_address() -> str:
        return await choice_server_address()


class RedisPull:

    DEFAULT_GROUP_ID = 'default_group_id'

    class Request:

        def __init__(
                self, id_: str, message: dict, expire_at: float,
                reverse_channel_addr: str, reverse_channels_cache: ExpiringDict
        ):
            self.__id = id_
            self.__message = message
            self.__reverse_channel_addr = reverse_channel_addr
            self.__reverse_channels_cache = reverse_channels_cache
            self.expire_at = expire_at

        def __str__(self):
            return f'@id: {self.__id}; reverse_channel: {self.__reverse_channel_addr}'

        @property
        def message(self) -> dict:
            return self.__message

        @property
        def reverse_channel_addr(self) -> str:
            return self.__reverse_channel_addr

        async def ack(self) -> bool:
            channel = self.__reverse_channels_cache.get(self.__reverse_channel_addr)
            if not channel:
                channel = AsyncRedisChannel(self.__reverse_channel_addr)
                self.__reverse_channels_cache[self.__reverse_channel_addr] = channel
            try:
                success = await channel.write(data={
                    '@id': self.__id,
                    '@type': ACK_MSG_TYPE,
                    'status': True
                })
                return success
            except RedisConnectionError:
                del self.__reverse_channels_cache[self.__reverse_channel_addr]
                return False

    def __init__(self):
        self.__channels = ExpiringDict(max_len=5, max_age_seconds=RedisPush.EXPIRE_SEC)

    class Listener:

        def __init__(self, channel: AsyncRedisGroup, reverse_channels_cache: ExpiringDict):
            self.__channel = channel
            self.__reverse_channels_cache = reverse_channels_cache

        async def get_one(self):
            while True:
                try:
                    ok, payload = await self.__channel.read(timeout=None)
                    if ok:
                        if payload.get('@type') == PUSH_MSG_TYPE:
                            request = RedisPull.Request(
                                id_=payload['@id'],
                                message=payload['message'],
                                expire_at=payload['expire_at'],
                                reverse_channel_addr=payload['reverse_channel'],
                                reverse_channels_cache=self.__reverse_channels_cache
                            )
                            return True, request
                    else:
                        return False, None
                except RedisConnectionError:
                    return False, None

        async def close(self):
            if self.__channel:
                await self.__channel.close()

        def __aiter__(self):
            return self

        @asyncio.coroutine
        def __anext__(self):
            """Asyncio iterator interface for listener"""
            while True:
                return (yield from self.get_one())

    def listen(self, address: str, group_id: str = DEFAULT_GROUP_ID, read_count: int = 1) -> Listener:
        if not group_id:
            group_id = self.DEFAULT_GROUP_ID
        channel = AsyncRedisGroup(address, group_id=group_id, read_count=read_count)
        listener = self.Listener(channel, self.__channels)
        return listener
