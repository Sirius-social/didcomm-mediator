import os.path
import uuid
from typing import Optional, Any, Tuple, Union

from databases import Database
from sqlalchemy import and_, or_, func, select

from app.utils import hash_string
from .models import agents, endpoints, routing_keys, users, global_settings, backups, pairwises


class BaseDBError(RuntimeError):
    pass


class DuplicateDBRecordError(BaseDBError):
    pass


class DBRecordDoesNotExists(BaseDBError):
    pass


GLOBAL_SETTING_PK = 1


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


async def load_pairwises(db: Database, filters: dict = None, offset: int = None, limit: int = None) -> list:
    sql = pairwises.select()
    if filters:
        cond = _build_pairwise_sql_cond(filters)
        if cond is not None:
            sql = sql.where(cond)
    if offset is not None:
        sql = sql.offset(offset)
    if limit is not None:
        sql = sql.limit(limit)
    rows = await db.fetch_all(query=sql)
    if rows:
        collection = []
        for row in rows:
            p = _restore_pairwise_from_row(row)
            collection.append(p)
        return collection
    else:
        return []


async def load_pairwises_count(db: Database, filters: dict = None) -> int:
    cond = _build_pairwise_sql_cond(filters) if filters else None
    if cond is not None:
        sql = select([func.count(pairwises.c.their_did)]).where(cond)
    else:
        sql = select([func.count(pairwises.c.their_did)])
    count = await db.execute(query=sql)
    return count


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


async def load_endpoint_via_routing_key(db: Database, routing_key: str) -> Optional[str]:
    sql = routing_keys.select().where(routing_keys.c.key == routing_key)
    row = await db.fetch_one(query=sql)
    if row:
        endpoint_uid = row['endpoint_uid']
        return endpoint_uid
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


async def create_user(db: Database, username: str, password: str) -> dict:
    sql = users.select().where(users.c.username == username)
    row = await db.fetch_one(query=sql)
    if row:
        raise DuplicateDBRecordError(f'User with username: "{username}" already exists!')
    else:
        sql = users.insert()
        values = {
            'id': hash_string(username),
            'username': username,
            'hashed_password': hash_string(password),
            'is_active': True
        }
        await db.execute(query=sql, values=values)
        user = await load_user(db, username)
        return user


async def load_user(db: Database, username: str, mute_errors: bool = False) -> Optional[dict]:
    sql = users.select().where(users.c.username == username)
    row = await db.fetch_one(query=sql)
    if row:
        return _restore_user_from_row(row)
    else:
        if mute_errors:
            return None
        else:
            raise DBRecordDoesNotExists(f'User with username: "{username}" does not exists!')


async def load_superuser(db: Database, mute_errors: bool = False) -> Optional[dict]:
    sql = users.select().where(users.c.is_active == True)
    row = await db.fetch_one(query=sql)
    if row:
        return _restore_user_from_row(row)
    else:
        if mute_errors:
            return None
        else:
            raise DBRecordDoesNotExists(f'No superusers!')


def check_password(user: dict, password: str) -> bool:
    return user['hashed_password'] == hash_string(password)


async def get_global_setting(db: Database, name: str) -> Optional[Any]:
    async with db.transaction():
        await db.execute(f"LOCK TABLE global_settings IN SHARE MODE;")
        sql = global_settings.select().where(global_settings.c.id == GLOBAL_SETTING_PK)
        row = await db.fetch_one(query=sql)
        if row:
            content = row['content']
            value = content.get(name, None)
            return value
        else:
            return None


async def set_global_setting(db: Database, name: str, value: Any):
    async with db.transaction():
        await db.execute(f"LOCK TABLE global_settings IN EXCLUSIVE MODE;")
        sql = global_settings.select().where(global_settings.c.id == GLOBAL_SETTING_PK)
        row = await db.fetch_one(query=sql)
        content = {}
        if row:
            content = row['content']
            content[name] = value
            sql = global_settings.update().where(global_settings.c.id == GLOBAL_SETTING_PK)
            values = {'content': content}
            await db.execute(query=sql, values=values)
        else:
            content[name] = value
            sql = global_settings.insert()
            values = {
                'id': GLOBAL_SETTING_PK,
                'content': content,
            }
            await db.execute(query=sql, values=values)


async def load_backup(db: Database, description: str) -> Tuple[bool, Optional[bytes], Optional[dict]]:
    """
    :return: success, backup-binary, context
    """
    sql = backups.select().where(backups.c.description == description)
    row = await db.fetch_one(query=sql)
    if row:
        binary = row['binary']
        context = row['context']
        return True, binary, context
    else:
        return False, None, None


async def dump_backup(db: Database, description: str, binary: bytes, context: dict = None):
    async with db.transaction():
        await db.execute(f"LOCK TABLE backups IN ROW EXCLUSIVE MODE;")
        sql = f"SELECT * FROM backups WHERE description = '{description}' FOR UPDATE;"
        row = await db.fetch_one(query=sql)
        if row:
            sql = backups.update().where(backups.c.description == description)
            await db.execute(query=sql, values={'binary': binary, 'context': context})
        else:
            sql = backups.insert()
            values = {
                'description': description,
                'binary': binary,
                'context': context
            }
            await db.execute(query=sql, values=values)


async def restore_path(db: Database, description: str, base_dir: str = None) -> Tuple[bool, Optional[str], Optional[dict]]:
    ok, binary, ctx = await load_backup(db, description)
    if ok:
        path = ctx.get('_path')
        is_dir = ctx.get('_is_dir')
        dump_file = '/tmp/' + uuid.uuid4().hex + '.tar.gz'
        with open(dump_file, 'w+b') as f:
            f.truncate(0)
            f.write(binary)
        try:
            if base_dir is None:
                base_dir = '/'
            else:
                path = os.path.join(base_dir, path[1:])
            exit_code = os.system(f'cd {base_dir} && tar -xvf {dump_file}')
            if exit_code == 0:
                return True, path, ctx
            else:
                return False, path, ctx
        finally:
            os.remove(dump_file)
    else:
        return False, None, None


async def dump_path(db: Database, description: str, path: str, context: dict = None):
    dump_file = '/tmp/' + uuid.uuid4().hex + '.tar.gz'
    if os.path.exists(path):
        try:
            exit_code = os.system(f'cd / && tar -czvf {dump_file} {path}')
            if exit_code == 0:
                with open(dump_file, 'rb') as f:
                    binary = f.read()
                    context['_path'] = path
                    context['_is_dir'] = os.path.isdir(path)
                    await dump_backup(db, description, binary, context)
            else:
                raise RuntimeError('Error while archive file')
        finally:
            os.remove(dump_file)
    elif os.path.isdir(path):
        pass
    else:
        raise RuntimeError(f'Path {path} does not exists')


async def reset_accounts(db: Database):
    sql = users.delete()
    await db.execute(query=sql)


async def reset_global_settings(db: Database):
    async with db.transaction():
        await db.execute(f"LOCK TABLE global_settings IN EXCLUSIVE MODE;")
        sql = global_settings.delete()
        await db.execute(query=sql)


def _build_pairwise_sql_cond(filters: dict):
    cond_items = []
    for key, value in filters.items():
        value = value + '%'
        if key == 'their_did':
            cond_items.append(pairwises.c.their_did.ilike(value))
        elif key == 'my_did':
            cond_items.append(pairwises.c.my_did.ilike(value))
        elif key == 'their_label':
            cond_items.append(pairwises.c.their_label.ilike(value))
    if cond_items:
        cond = or_(*cond_items)
    else:
        cond = None
    return cond


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


def _restore_pairwise_from_row(row) -> dict:
    return {
        'their_did': row['their_did'],
        'their_verkey': row['their_verkey'],
        'my_did': row['my_did'],
        'my_verkey': row['my_verkey'],
        'metadata': row['metadata'],
        'their_label': row['their_label']
    }


def _restore_routing_key_from_row(row) -> dict:
    return {
        'id': row['id'],
        'key': row['key'],
        'endpoint_uid': row['endpoint_uid'],
    }


def _restore_user_from_row(row) -> dict:
    return {
        'id': row['id'],
        'username': row['username'],
        'hashed_password': row['hashed_password'],
        'is_active': row['is_active']
    }
