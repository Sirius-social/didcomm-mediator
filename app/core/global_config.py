from typing import Optional

import aiomemcached
from databases import Database

import app.settings
import settings

from .repo import Repo


class GlobalConfig:

    CFG_WEBROOT = 'webroot'
    CFG_SSL_OPTION = 'ssl'
    CFG_FIREBASE = 'firebase'

    def __init__(self, db: Database, memcached: aiomemcached.Client = None):
        self.__repo = Repo(db, memcached)

    async def get_ssl_option(self) -> Optional[str]:
        value = await self.__repo.get_global_setting(self.CFG_SSL_OPTION)
        return value

    async def set_ssl_option(self, value: str):
        await self.__repo.set_global_setting(self.CFG_SSL_OPTION, value)

    async def get_webroot(self) -> Optional[str]:
        value = await self.__repo.get_global_setting(self.CFG_WEBROOT)
        return app.settings.WEBROOT or value

    async def set_webroot(self, value: str):
        if value.endswith('/'):
            value = value[:-1]
        await self.__repo.set_global_setting(self.CFG_WEBROOT, value)

    async def get_any_option(self, name: str) -> Optional[str]:
        value = await self.__repo.get_global_setting(name)
        return value

    async def set_any_option(self, name: str, value: str):
        await self.__repo.set_global_setting(name, value)

    async def get_firebase_secret(self) -> (Optional[str], Optional[str]):
        """
        :return: api_key, sender_id
        """
        value = await self.__repo.get_global_setting(self.CFG_FIREBASE)
        if not value:
            value = {}
        if settings.FIREBASE_API_KEY:
            api_key = settings.FIREBASE_API_KEY
        else:
            api_key = value.get('api_key')
        if settings.FIREBASE_SENDER_ID:
            sender_id = settings.FIREBASE_SENDER_ID
        else:
            sender_id = value.get('sender_id')
        return api_key, sender_id

    async def set_firebase_secret(self, api_key: str, sender_id):
        value = {
            'api_key': api_key,
            'sender_id': sender_id
        }
        await self.__repo.set_global_setting(self.CFG_FIREBASE, value)
