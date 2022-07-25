import base64
from dataclasses import dataclass
from typing import Union, Optional, List, Any

from sirius_sdk.agent.aries_rfc.base import AriesProtocolMessage, RegisterMessage, VALID_DOC_URI, AriesProblemReport

from rfc.decorators import *


class BusOperation(AriesProtocolMessage, metaclass=RegisterMessage):
    """Aries concept 0478 Messages implementation

    https://github.com/hyperledger/aries-rfcs/tree/main/concepts/0478-coprotocols
    """
    DOC_URI = VALID_DOC_URI[0]
    PROTOCOL = 'bus'

    @dataclass
    class Cast:
        thid: Union[str, List[str]] = None
        recipient_vk: Union[str, List[str]] = None
        sender_vk: Union[str, List[str]] = None
        protocols: List[str] = None

        def validate(self) -> bool:
            if self.recipient_vk or self.sender_vk:
                if not self.protocols:
                    return False
            return True

        def as_json(self) -> dict:
            js = {}
            if self.thid:
                js['thid'] = self.thid
            if self.protocols:
                js['protocols'] = sorted(self.protocols)
            if self.sender_vk:
                js['sender_vk'] = self.sender_vk if isinstance(self.sender_vk, str) else sorted(self.sender_vk)
            if self.recipient_vk:
                js['recipient_vk'] = self.recipient_vk if isinstance(self.recipient_vk, str) else sorted(self.recipient_vk)
            return js

    @property
    def return_route(self) -> Optional[str]:
        return self.get('~transport', {}).get('return_route', None)

    @return_route.setter
    def return_route(self, value: str):
        transport = self.get('~transport', {})
        transport['return_route'] = value
        self['~transport'] = transport


class BusSubscribeRequest(BusOperation, metaclass=RegisterMessage):
    NAME = 'subscribe'

    def __init__(self, cast: Union[BusOperation.Cast, dict] = None, parent_thread_id: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(cast, dict):
            cast = BusOperation.Cast(**cast)
        self.__store_cast(cast)
        if parent_thread_id:
            set_parent_thread_id(self, parent_thread_id)

    @property
    def return_route(self) -> Optional[str]:
        return self.get('~transport', {}).get('return_route', None)

    @return_route.setter
    def return_route(self, value: str):
        transport = self.get('~transport', {})
        transport['return_route'] = value
        self['~transport'] = transport

    @property
    def cast(self) -> BusOperation.Cast:
        kwargs = self.get('cast', {})
        return self.Cast(**kwargs)

    @property
    def parent_thread_id(self) -> Optional[str]:
        return get_parent_thread_id(self)

    def __store_cast(self, value: BusOperation.Cast = None):
        js = {}
        if value is not None:
            js = value.as_json()
        if js:
            self['cast'] = js
        elif 'cast' in self:
            del self['cast']


class BusBindResponse(BusOperation, metaclass=RegisterMessage):
    NAME = 'bind'

    def __init__(
            self, thread_id: Union[str, List[str]] = None,
            active: bool = None, parent_thread_id: str = None, aborted: bool = None, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        if thread_id:
            set_thread_id(self, thread_id)
        if active is not None:
            self['active'] = active
        if parent_thread_id:
            set_parent_thread_id(self, parent_thread_id)
        if aborted is not None:
            self['aborted'] = aborted

    @property
    def active(self) -> Optional[bool]:
        return self.get('active', None)

    @property
    def aborted(self) -> Optional[bool]:
        return self.get('aborted', None)

    @property
    def thread_id(self) -> Optional[Union[str, List[str]]]:
        return get_thread_id(self)

    @property
    def parent_thread_id(self) -> Optional[str]:
        return get_parent_thread_id(self)


class BusUnsubscribeRequest(BusBindResponse, metaclass=RegisterMessage):
    NAME = 'unsubscribe'

    def __init__(
            self, thread_id: Union[str, List[str]] = None,
            need_answer: bool = None, parent_thread_id: str = None, aborted: bool = None, *args, **kwargs
    ):
        super().__init__(thread_id, *args, **kwargs)
        if need_answer is not None:
            self['need_answer'] = need_answer
        if parent_thread_id:
            set_parent_thread_id(self, parent_thread_id)
        if aborted is not None:
            self['aborted'] = aborted

    @property
    def need_answer(self) -> Optional[bool]:
        return self.get('need_answer', None)

    @need_answer.setter
    def need_answer(self, value: bool):
        self['need_answer'] = value

    @property
    def aborted(self) -> Optional[bool]:
        return self.get('aborted', None)

    @property
    def parent_thread_id(self) -> Optional[str]:
        return get_parent_thread_id(self)


class BusPublishRequest(BusBindResponse, metaclass=RegisterMessage):
    NAME = 'publish'

    def __init__(self, thread_id: Union[str, List[str]] = None, payload: Any = None, *args, **kwargs):
        super().__init__(thread_id, *args, **kwargs)
        if payload:
            self.payload = payload

    @property
    def payload(self) -> Any:
        payload = self.get('payload', {})
        if payload:
            typ = payload.get('type')
            data = payload.get('data')
            if typ == 'application/base64':
                return base64.b64decode(data.encode('ascii'))
            else:
                return data
        else:
            return None

    @payload.setter
    def payload(self, value: Any):
        if isinstance(value, dict):
            self['payload'] = value
        elif isinstance(value, bytes):
            self['payload'] = {
                'type': 'application/base64',
                'data': base64.b64encode(value).decode('ascii')
            }
        else:
            self['payload'] = {
                'type': '',
                'data': value
            }


class BusEvent(BusPublishRequest, metaclass=RegisterMessage):
    NAME = 'event'


class BusPublishResponse(BusBindResponse, metaclass=RegisterMessage):
    NAME = 'publish-result'

    def __init__(self, thread_id: Union[str, List[str]] = None, recipients_num: int = None, *args, **kwargs):
        super().__init__(thread_id, *args, **kwargs)
        if recipients_num is not None:
            self['recipients_num'] = recipients_num

    @property
    def recipients_num(self) -> Optional[int]:
        return self.get('recipients_num', None)


class BusProblemReport(AriesProblemReport, metaclass=RegisterMessage):
    DOC_URI = VALID_DOC_URI[0]
    PROTOCOL = BusOperation.PROTOCOL
