import uuid
from typing import Optional

from databases import Database

from .models import agents


async def ensure_agent_exists(db: Database, did: str, verkey: str, metadata: dict = None):
    agent = await load_agent(db, did)
    if agent:
        if agent['verkey'] != verkey or (agent['metadata'] != metadata and metadata is not None):
            sql = agents.update().where(agents.c.did == did)
            values = {
                "verkey": verkey,
                "metadata": metadata
            }
            await db.execute(query=sql, values=values)
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
            'metadata': row['metadata']
        }
    else:
        return None
