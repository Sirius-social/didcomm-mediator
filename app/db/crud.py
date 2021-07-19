import uuid
from typing import Optional

from databases import Database
from sqlalchemy import and_

from .models import agents, endpoints, routing_keys


async def ensure_agent_exists(db: Database, did: str, verkey: str, metadata: dict = None, fcm_device_id: str = None):
    async with db.transaction():
        # remove records with same verkey
        cond = and_(agents.c.verkey == verkey, agents.c.did != did)
        sql = agents.select().where(cond)
        rows = await db.fetch_all(query=sql)
        if rows:
            sql = agents.delete().where(cond)
            await db.execute(query=sql)
        # custom operations
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


async def ensure_endpoint_exists(
        db: Database, uid: str, redis_pub_sub: str = None,
        agent_id: str = None, verkey: str = None, fcm_device_id: str = None
):
    async with db.transaction():
        if verkey:
            # remove records with same verkey
            cond = and_(endpoints.c.verkey == verkey, endpoints.c.uid != uid)
            sql = endpoints.select().where(cond)
            rows = await db.fetch_all(query=sql)
            if rows:
                sql = endpoints.delete().where(cond)
                await db.execute(query=sql)
        # custom operations
        endpoint = await load_endpoint(db, uid)
        if endpoint:
            fields_to_update = {}
            if redis_pub_sub is not None and endpoint['redis_pub_sub'] != redis_pub_sub:
                fields_to_update['redis_pub_sub'] = redis_pub_sub
            if agent_id is not None and endpoint['agent_id'] != agent_id:
                fields_to_update['agent_id'] = agent_id
            if redis_pub_sub is not None and endpoint['redis_pub_sub'] != redis_pub_sub:
                fields_to_update['redis_pub_sub'] = redis_pub_sub
            if verkey is not None and endpoint['verkey'] != verkey:
                fields_to_update['verkey'] = verkey
            if fcm_device_id is not None and endpoint['fcm_device_id'] != fcm_device_id:
                fields_to_update['fcm_device_id'] = fcm_device_id
            if fields_to_update:
                sql = endpoints.update().where(endpoints.c.uid == uid)
                await db.execute(query=sql, values=fields_to_update)
        else:
            sql = endpoints.insert()
            values = {
                "uid": uid,
                "redis_pub_sub": redis_pub_sub,
                "agent_id": agent_id,
                "verkey": verkey,
                "fcm_device_id": fcm_device_id
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


async def load_endpoint_via_verkey(db: Database, verkey: str) -> Optional[dict]:
    sql = endpoints.select().where(endpoints.c.verkey == verkey)
    row = await db.fetch_one(query=sql)
    if row:
        return _restore_endpoint_from_row(row)
    else:
        return None


async def add_routing_key(db: Database, endpoint_uid: str, key: str) -> dict:
    sql = routing_keys.insert()
    values = {
        "endpoint_uid": endpoint_uid,
        "key": key,
    }
    pk = await db.execute(query=sql, values=values)
    resp = {
        'id': pk,
    }
    resp.update(values)
    return resp


async def remove_routing_key(db: Database, endpoint_uid: str, key: str):
    sql = routing_keys.delete().where(and_(routing_keys.c.key == key, routing_keys.c.endpoint_uid == endpoint_uid))
    await db.execute(query=sql)


async def list_routing_key(db: Database, endpoint_uid: str) -> list:
    sql = routing_keys.select().where(routing_keys.c.endpoint_uid == endpoint_uid).order_by("id")
    rows = await db.fetch_all(query=sql)
    resp = []
    for row in rows:
        resp.append(_restore_routing_key_from_row(row))
    return resp


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
        'verkey': row['verkey'],
        'agent_id': row['agent_id'],
        'redis_pub_sub': row['redis_pub_sub'],
        'fcm_device_id': row['fcm_device_id']
    }


def _restore_routing_key_from_row(row) -> dict:
    return {
        'id': row['id'],
        'key': row['key'],
        'endpoint_uid': row['endpoint_uid'],
    }
