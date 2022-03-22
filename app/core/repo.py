import json
import logging
from typing import Union, Optional, Any

import aiomemcached
from databases import Database

import app.db.crud
from app.settings import MEMCACHED as MEMCACHED_SERVER


class Repo:

    """Repository is wrapper over database who knows how to cache database queries
        and manage caching data. In other words it is Smart database operator who optimize DKMS access
    """

    NAMESPACE_AGENTS = 'agents'
    NAMESPACE_AGENTS_VERKEYS = 'agents_verkeys'
    NAMESPACE_ENDPOINTS = 'endpoints'
    NAMESPACE_ENDPOINTS_VERKEYS = 'endpoints_verkeys'
    NAMESPACE_ROUTING_KEYS = 'routing_keys'
    NAMESPACE_GLOBAL_SETTINGS = 'global_settings'
    MEMCACHED_TIMEOUT = 60

    def __init__(self, db: Database, memcached: aiomemcached.Client = None):
        self.__db = db
        self.__memcached = memcached or aiomemcached.Client(host=MEMCACHED_SERVER, pool_minsize=1)

    @property
    def db(self) -> Database:
        return self.__db

    @property
    def memcached(self) -> aiomemcached.Client:
        return self.__memcached

    async def ensure_agent_exists(self, did: str, verkey: str, metadata: dict = None, fcm_device_id: str = None):
        await self._delete_cache(did, namespace=self.NAMESPACE_AGENTS)
        agent_verkey = await self._get_cache(did, namespace=self.NAMESPACE_AGENTS_VERKEYS)
        if agent_verkey:
            await self._delete_cache(agent_verkey, namespace=self.NAMESPACE_AGENTS)
            await self._delete_cache(did, namespace=self.NAMESPACE_AGENTS_VERKEYS)
        await app.db.crud.ensure_agent_exists(self.__db, did, verkey, metadata, fcm_device_id)

    async def load_agent(self, did: str) -> Optional[dict]:
        cached = await self._get_cache(did, namespace=self.NAMESPACE_AGENTS)
        if cached:
            return cached
        else:
            agent = await app.db.crud.load_agent(self.__db, did)
            if agent:
                await self._set_cache(did, agent, namespace=self.NAMESPACE_AGENTS)
                if agent['verkey']:
                    await self._set_cache(did, agent['verkey'], namespace=self.NAMESPACE_AGENTS_VERKEYS)
            return agent

    async def load_agent_via_verkey(self, verkey: str) -> Optional[dict]:
        cached = await self._get_cache(verkey, namespace=self.NAMESPACE_AGENTS)
        if cached:
            return cached
        else:
            agent = await app.db.crud.load_agent_via_verkey(self.__db, verkey)
            if agent:
                await self._set_cache(verkey, agent, namespace=self.NAMESPACE_AGENTS)
                if agent['verkey']:
                    await self._set_cache(agent['did'], agent['verkey'], namespace=self.NAMESPACE_AGENTS_VERKEYS)
            return agent

    async def ensure_endpoint_exists(
            self, uid: str, redis_pub_sub: str = None,
            agent_id: str = None, verkey: str = None, fcm_device_id: str = None
    ):
        await self._delete_cache(uid, namespace=self.NAMESPACE_ENDPOINTS)
        endpoint_verkey = await self._get_cache(uid, namespace=self.NAMESPACE_AGENTS_VERKEYS)
        if endpoint_verkey:
            await self._delete_cache(endpoint_verkey, namespace=self.NAMESPACE_AGENTS)
            await self._delete_cache(uid, namespace=self.NAMESPACE_AGENTS_VERKEYS)
        await app.db.crud.ensure_endpoint_exists(self.__db, uid, redis_pub_sub, agent_id, verkey, fcm_device_id)

    async def load_endpoint(self, uid: str) -> Optional[dict]:
        cached = await self._get_cache(uid, namespace=self.NAMESPACE_ENDPOINTS)
        if cached:
            return cached
        else:
            endpoint = await app.db.crud.load_endpoint(self.__db, uid)
            if endpoint:
                await self._set_cache(uid, endpoint, namespace=self.NAMESPACE_ENDPOINTS)
                if endpoint['verkey']:
                    await self._set_cache(uid, endpoint['verkey'], namespace=self.NAMESPACE_ENDPOINTS_VERKEYS)
            return endpoint

    async def load_endpoint_via_verkey(self, verkey: str) -> Optional[dict]:
        cached = await self._get_cache(verkey, namespace=self.NAMESPACE_ENDPOINTS)
        if cached:
            return cached
        else:
            endpoint = await app.db.crud.load_endpoint_via_verkey(self.__db, verkey)
            if endpoint:
                await self._set_cache(verkey, endpoint, namespace=self.NAMESPACE_ENDPOINTS)
                if endpoint['verkey']:
                    await self._set_cache(endpoint['uid'], endpoint['verkey'], namespace=self.NAMESPACE_ENDPOINTS_VERKEYS)
            return endpoint

    async def load_endpoint_via_routing_key(self, routing_key) -> Optional[dict]:
        cached = await self._get_cache(routing_key, namespace=self.NAMESPACE_ENDPOINTS)
        if cached:
            return cached
        else:
            endpoint_uid = await app.db.crud.load_endpoint_via_routing_key(self.__db, routing_key)
            if endpoint_uid:
                endpoint = await self.load_endpoint(endpoint_uid)
                if endpoint:
                    await self._set_cache(routing_key, endpoint, namespace=self.NAMESPACE_ENDPOINTS)
                return endpoint
            else:
                return None

    async def add_routing_key(self, endpoint_uid: str, key: str) -> dict:
        await self._delete_cache(endpoint_uid, namespace=self.NAMESPACE_ROUTING_KEYS)
        key = await app.db.crud.add_routing_key(self.__db, endpoint_uid, key)
        return key

    async def remove_routing_key(self, endpoint_uid: str, key: str):
        await self._delete_cache(endpoint_uid, namespace=self.NAMESPACE_ROUTING_KEYS)
        await app.db.crud.remove_routing_key(self.__db, endpoint_uid, key)

    async def list_routing_key(self, endpoint_uid: str) -> list:
        cached = await self._get_cache(endpoint_uid, namespace=self.NAMESPACE_ROUTING_KEYS)
        if cached:
            return cached
        else:
            collection = await app.db.crud.list_routing_key(self.__db, endpoint_uid)
            await self._set_cache(endpoint_uid, collection, namespace=self.NAMESPACE_ROUTING_KEYS)
            return collection

    async def get_global_setting(self, name: str) -> Optional[Any]:
        cached = await self._get_cache(name, namespace=self.NAMESPACE_GLOBAL_SETTINGS)
        if cached:
            return cached.get('value', None)
        else:
            value = await app.db.crud.get_global_setting(self.__db, name)
            await self._set_cache(name, {'value': value}, namespace=self.NAMESPACE_GLOBAL_SETTINGS)
            return value

    async def set_global_setting(self, name: str, value: Any):
        await self._delete_cache(name, namespace=self.NAMESPACE_GLOBAL_SETTINGS)
        await app.db.crud.set_global_setting(self.__db, name, value)

    async def _set_cache(self, key: str, value: Union[dict, str, list], exp_time: int = None, namespace: str = None):
        if namespace:
            _key = f'{namespace}:{key}'
        else:
            _key = key
        _value = json.dumps({
            'type': 'obj' if type(value) is dict else 'str',
            'value': json.dumps(value) if type(value) is dict else value
        })
        try:
            await self.__memcached.set(_key.encode(), _value.encode(), exptime=exp_time or self.MEMCACHED_TIMEOUT)
        except Exception as e:
            logging.exception('MemCached exception')

    async def _get_cache(self, key: str, namespace: str = None) -> Optional[Union[dict, str, list]]:
        if namespace:
            _key = f'{namespace}:{key}'
        else:
            _key = key
        try:
            value_b, _ = await self.__memcached.get(_key.encode())
        except Exception as e:
            logging.exception('MemCached exception')
            return None
        value = value_b.decode() if value_b else None
        if value:
            descr = json.loads(value)
            typ = descr['type']
            value = descr['value']
            if typ == 'obj':
                value = json.loads(value)
            return value
        else:
            return None

    async def _delete_cache(self, key: str, namespace: str = None):
        if namespace:
            _key = f'{namespace}:{key}'
        else:
            _key = key
        try:
            await self.__memcached.delete(_key.encode())
        except Exception as e:
            logging.exception('MemCached exception')
