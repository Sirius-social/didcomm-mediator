import uuid
from typing import Optional

from databases import Database

from .models import agents, endpoints


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


async def ensure_endpoint_exists(db: Database, uid: str, redis_pub_sub: str = None, agent_id: str = None):
    endpoint = await load_endpoint(db, uid)
    if endpoint:
        fields_to_update = {}
        if redis_pub_sub is not None and endpoint['redis_pub_sub'] != redis_pub_sub:
            fields_to_update['redis_pub_sub'] = redis_pub_sub
        if agent_id is not None and endpoint['agent_id'] != agent_id:
            fields_to_update['agent_id'] = agent_id
        if redis_pub_sub is not None and endpoint['redis_pub_sub'] != redis_pub_sub:
            fields_to_update['redis_pub_sub'] = redis_pub_sub
        if fields_to_update:
            sql = endpoints.update().where(endpoints.c.uid == uid)
            await db.execute(query=sql, values=fields_to_update)
    else:
        sql = endpoints.insert()
        values = {
            "uid": uid,
            "redis_pub_sub": redis_pub_sub,
            "agent_id": agent_id
        }
        await db.execute(query=sql, values=values)


async def load_agent(db: Database, did: str) -> Optional[dict]:
    sql = agents.select().where(agents.c.did == did)
    row = await db.fetch_one(query=sql)
    if row:
        return _restore_agent_from_row(row)
    else:
        return None


async def load_endpoint(db: Database, uid: str) -> Optional[dict]:
    sql = endpoints.select().where(endpoints.c.uid == uid)
    row = await db.fetch_one(query=sql)
    if row:
        return _restore_endpoint_from_row(row)
    else:
        return None


async def load_agent_via_verkey(db: Database, verkey: str) -> Optional[dict]:
    sql = agents.select().where(agents.c.verkey == verkey)
    row = await db.fetch_one(query=sql)
    if row:
        return _restore_agent_from_row(row)
    else:
        return None


def _restore_agent_from_row(row) -> dict:
    return {
        'id': row['id'],
        'did': row['did'],
        'verkey': row['verkey'],
        'metadata': row['metadata'],
        'fcm_device_id': row['fcm_device_id']
    }


def _restore_endpoint_from_row(row) -> dict:
    return {
        'uid': row['uid'],
        'agent_id': row['agent_id'],
        'redis_pub_sub': row['redis_pub_sub']
    }
