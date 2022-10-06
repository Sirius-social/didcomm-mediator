import json
import base64
from typing import Dict, Any, Optional

from app import settings
from app.db.models import key_value_storage as table
from databases import Database
from sqlalchemy import and_

from sirius_sdk.abstract.storage import AbstractKeyValueStorage
from sirius_sdk.agent.wallet.abstract import AbstractNonSecrets


class DatabaseKeyValueStorage(AbstractKeyValueStorage):

    def __init__(self, engine: Database = None):
        if engine is None:
            self.__engine = Database(settings.SQLALCHEMY_DATABASE_URL)
        else:
            self.__engine = engine
        self.__selected_db = 'default'

    async def select_db(self, db_name: str):
        self.__selected_db = db_name

    async def set(self, key: str, value: Any):
        cond = and_(
            table.c.namespace == self.__selected_db,
            table.c.key == key
        )
        sql = table.select().where(cond)
        row = await self.__engine.fetch_one(query=sql)
        if row:
            sql = table.update().where(table.c.id == row['id'])
            values = {
                'value': self.__serialize(value)
            }
        else:
            sql = table.insert()
            values = {
                'namespace': self.__selected_db,
                'key': key,
                'value': self.__serialize(value)
            }
        await self.__engine.execute(query=sql, values=values)

    async def get(self, key: str) -> Optional[Any]:
        cond = and_(
            table.c.namespace == self.__selected_db,
            table.c.key == key
        )
        sql = table.select().where(cond)
        row = await self.__engine.fetch_one(query=sql)
        if row is None:
            return None
        else:
            payload = row['value']
            return self.__deserialize(payload)

    async def delete(self, key: str):
        cond = and_(
            table.c.namespace == self.__selected_db,
            table.c.key == key
        )
        sql = table.delete().where(cond)
        await self.__engine.execute(query=sql)

    async def items(self) -> Dict:
        cond = and_(
            table.c.namespace == self.__selected_db,
        )
        sql = table.select().where(cond)
        rows = await self.__engine.fetch_all(query=sql)
        items = {}
        for row in rows:
            key = row['key']
            value = self.__deserialize(row['value'])
            items[key] = value
        return items

    @staticmethod
    def __serialize(value: Any) -> str:
        serialized = value
        content_type = None
        if type(value) is str:
            content_type = 'text'
            serialized = value
        elif type(value) is bytes:
            content_type = 'base64'
            serialized = base64.b64encode(value).decode()
        elif type(value) in [dict, list]:
            content_type = 'json'
            serialized = value
        elif type(value) is int:
            content_type = 'int'
            serialized = str(value)
        payload = json.dumps({
            'content_type': content_type,
            'serialized': serialized
        })
        return payload

    @staticmethod
    def __deserialize(payload: str) -> Any:
        meta = json.loads(payload)
        content_type = meta['content_type']
        serialized = meta['serialized']
        if content_type in ['text', 'json', None]:
            return serialized
        elif content_type == 'base64':
            return base64.b64decode(serialized).decode()
        elif content_type == 'int':
            return int(serialized)
        else:
            return serialized
