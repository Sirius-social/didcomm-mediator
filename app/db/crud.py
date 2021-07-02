import uuid
from typing import Optional

from databases import Database

from .models import agents


async def ensure_agent_exists(db: Database, did: str, verkey: str, metadata: dict = None, fcm_device_id: str = None):
    agent = await load_agent(db, did)
    if agent:
        fields_to_update = {}
        if agent['verkey'] != verkey:
            fields_to_update['verkey'] = verkey
        if metadata is not None and agent['metadata'] != metadata:
            fields_to_update['metadata'] = metadata
        if fcm_device_id is not None and agent['fcm_device_id'] != fcm_device_id:
            fields_to_update['fcm_device_id'] = fcm_device_id
        if fields_to_update:
            sql = agents.update().where(agents.c.did == did)
            await db.execute(query=sql, values=fields_to_update)
    else:
        sql = agents.insert()
        values = {
            "did": did,
            "verkey": verkey,
            "id": uuid.uuid4().hex
        }
        await db.execute(query=sql, values=values)


async def load_agent(db: Database, did: str) -> Optional[dict]:
    sql = agents.select().where(agents.c.did == did)
    row = await db.fetch_one(query=sql)
    if row:
        return {
            'id': row['id'],
            'did': row['did'],
            'verkey': row['verkey'],
            'metadata': row['metadata'],
            'fcm_device_id': row['fcm_device_id']
        }
    else:
        return None
