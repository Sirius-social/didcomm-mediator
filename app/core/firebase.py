import uuid
import asyncio

from databases import Database
from aiofcm import FCM, Message, PRIORITY_HIGH

from app.core.redis import AsyncRedisChannel
from app.core.singletons import GlobalMemcachedClient
from app.core.global_config import GlobalConfig
from app.settings import FIREBASE_API_KEY, FIREBASE_SENDER_ID


class FirebaseMessages:

    __instances = {}
    MAX_CONNECTIONS = 1000

    def __init__(self, db: Database):
        self.__cfg = GlobalConfig(db=db, memcached=GlobalMemcachedClient.get())

    async def enabled(self) -> bool:
        api_key, sender_id = await self.__cfg.get_firebase_secret()
        return (api_key is not None) and (sender_id is not None)

    async def send(self, device_id: str, msg: dict, msg_id: str = None) -> bool:
        if device_id.startswith('redis://'):
            ch = AsyncRedisChannel(device_id)
            success = await ch.write(msg)
            return success
        else:
            if not FIREBASE_API_KEY:
                raise RuntimeError('You must set Firebase API-KEY')
            api_key, sender_id = await self.__cfg.get_firebase_secret()
            fcm = self.get_fcm(api_key, sender_id)
            message = Message(
                device_token=device_id,
                data=msg,
                message_id=msg_id or uuid.uuid4().hex,
                priority=PRIORITY_HIGH
            )
            response = await fcm.send_message(message)
            return response.is_successful

    @staticmethod
    def _get_cur_loop_id() -> int:
        # Memcached Aio api is critical to current running loop
        cur_loop = asyncio.get_event_loop()
        if cur_loop:
            cur_loop_id = id(cur_loop)
        else:
            cur_loop_id = 0
        return cur_loop_id

    @classmethod
    def get_fcm(cls, api_key: str, sender_id: str) -> FCM:
        cur_loop_id = cls._get_cur_loop_id()
        instance_key = f'{cur_loop_id}://{api_key}/{sender_id}'
        inst = cls.__instances.get(instance_key)
        if not inst:
            inst = FCM(sender_id=FIREBASE_SENDER_ID, api_key=FIREBASE_API_KEY, max_connections=cls.MAX_CONNECTIONS)
            cls.__instances[cur_loop_id] = inst
        return inst
