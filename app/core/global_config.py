from typing import Optional

import aiomemcached
from databases import Database

import app.settings

from .repo import Repo


class GlobalConfig:

    CFG_WEBROOT = 'webroot'
    CFG_SSL_OPTION = 'ssl'

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
