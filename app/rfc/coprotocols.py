from dataclasses import dataclass
from typing import Union, Optional, List

from sirius_sdk.agent.aries_rfc.base import AriesProtocolMessage, RegisterMessage, VALID_DOC_URI, AriesProblemReport


class BusOperation(AriesProtocolMessage, metaclass=RegisterMessage):
    """Aries concept 0478 Messages implementation

    hhttps://github.com/hyperledger/aries-rfcs/tree/main/concepts/0478-coprotocols
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

    def __init__(self, cast: Cast = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__store_cast(cast)

    @property
    def cast(self) -> Cast:
        kwargs = self.get('cast', {})
        return self.Cast(**kwargs)

    def __store_cast(self, value: Cast = None):
        kwargs = {}
        if value is not None:
            if value.thid:
                kwargs['thid'] = value.thid
            if value.protocols:
                kwargs['protocols'] = value.thid
            if value.sender_vk:
                kwargs['sender_vk'] = value.sender_vk
            if value.recipient_vk:
                kwargs['recipient_vk'] = value.recipient_vk
        if kwargs:
            self['cast'] = kwargs
        elif 'cast' in self:
            del self['cast']


class BusSubscribeOperation(BusOperation, metaclass=RegisterMessage):
    NAME = 'subscribe'

    def __init__(self, cast: BusOperation.Cast = None, *args, **kwargs):
        super().__init__(cast, *args, **kwargs)


class BusUnsubscribeOperation(BusOperation, metaclass=RegisterMessage):
    NAME = 'unsubscribe'


class BusProblemReport(AriesProblemReport, metaclass=RegisterMessage):
    PROTOCOL = BusOperation.PROTOCOL
