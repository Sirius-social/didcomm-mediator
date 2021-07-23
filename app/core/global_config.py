from typing import Optional

import aiomemcached
from databases import Database

import app.settings

from .repo import Repo


class GlobalConfig:

    CFG_WEBROOT = 'webroot'

    def __init__(self, db: Database, memcached: aiomemcached.Client = None):
        self.__repo = Repo(db, memcached)

    async def get_webroot(self) -> Optional[str]:
        value = await self.__repo.get_global_setting(self.CFG_WEBROOT)
        return app.settings.WEBROOT or value

    async def set_webroot(self, value: str):
        if value.endswith('/'):
            value = value[:-1]
        await self.__repo.set_global_setting(self.CFG_WEBROOT, value)
