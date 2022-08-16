import json
import uuid
import math
import asyncio
import datetime
from collections import OrderedDict
from dataclasses import dataclass
from typing import Union, Optional, List, OrderedDict as OrderedDictAlias

from sirius_sdk.agent.aries_rfc.base import AriesProtocolMessage, RegisterMessage, VALID_DOC_URI, AriesProblemReport


class BasePickUpMessage(AriesProtocolMessage, metaclass=RegisterMessage):
    """Aries 0212 Pickup Protocol

    https://github.com/hyperledger/aries-rfcs/tree/main/features/0212-pickup

    Draft: https://hackmd.io/@andrewwhitehead/SJw9Ead2N
    """
    DOC_URI = VALID_DOC_URI[0]
    PROTOCOL = 'messagepickup'

    @dataclass
    class BatchedMessage:
        msg_id: str = None
        message: Union[dict, str] = None

    @property
    def return_route(self) -> Optional[str]:
        return self.get('~transport', {}).get('return_route', None)

    @return_route.setter
    def return_route(self, value: str):
        transport = self.get('~transport', {})
        transport['return_route'] = value
        self['~transport'] = transport


class PickUpStatusRequest(BasePickUpMessage):
    NAME = 'status-request'


class PickUpStatusResponse(BasePickUpMessage):
    NAME = 'status'

    def __init__(
            self,
            message_count: int = None,
            duration_limit: int = None, last_added_time: str = None,
            last_delivered_time: str = None, last_removed_time: str = None,
            *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        if message_count is not None:
            self['message_count'] = message_count
        if duration_limit is not None:
            self['duration_limit'] = duration_limit
        if last_added_time is not None:
            self['last_added_time'] = last_added_time
        if last_delivered_time is not None:
            self['last_delivered_time'] = last_delivered_time
        if last_removed_time is not None:
            self['last_removed_time'] = last_removed_time

    """Required Status Properties:"""
    @property
    def message_count(self) -> Optional[int]:
        # The number of messages in the queue
        return self.get('message_count', None)

    """Optional Status Properties"""
    @property
    def duration_limit(self) -> Optional[int]:
        # The maximum duration in seconds that a message may stay in the queue
        # without being delivered (may be zero for no limit)
        return self.get('duration_limit', None)

    def last_added_time(self) -> Optional[str]:
        # A timestamp representing the last time a message was added to the queue
        return self.get('last_added_time', None)

    @property
    def last_removed_time(self) -> Optional[str]:
        # A timestamp representing the last time one or more messages was removed from the queue
        return self.get('last_removed_time', None)


class PickUpBatchRequest(BasePickUpMessage):
    NAME = 'batch-pickup'

    def __init__(self, batch_size: int = None, delay_timeout: float = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if batch_size is not None:
            self['batch_size'] = batch_size
        if delay_timeout is not None:
            self['~timing'] = {'delay_milli': math.ceil(delay_timeout*1000)}

    @property
    def batch_size(self) -> Optional[str]:
        return self.get('batch_size', None)

    @property
    def delay_timeout(self) -> Optional[float]:
        delay_milli = self.get('~timing', {}).get('delay_milli', None)
        if delay_milli is not None:
            return delay_milli/1000


class PickUpBatchResponse(BasePickUpMessage):

    NAME = 'batch'

    @property
    def filled(self) -> bool:
        return (self.msg_id is not None) and (self.message is not None)

    def __init__(self, messages: List[BasePickUpMessage.BatchedMessage] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if messages is not None:
            attach = []
            for msg in messages:
                attach.append({
                    '@id': msg.msg_id,
                    'message': msg.message
                })
            self['messages~attach'] = attach

    @property
    def messages(self) -> List[BasePickUpMessage.BatchedMessage]:
        messages = []
        for attach in self.get('messages~attach', []):
            message = BasePickUpMessage.BatchedMessage(
                msg_id=attach.get('@id', None),
                message=attach.get('message', None)
            )
            messages.append(message)
        return messages


class PickUpListRequest(BasePickUpMessage):
    NAME = 'list-pickup'

    def __init__(self, message_ids: List[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if message_ids is not None:
            self['message_ids'] = message_ids

    @property
    def message_ids(self) -> List[str]:
        return self.get('message_ids', [])


class PickUpListResponse(BasePickUpMessage):
    NAME = 'list-response'

    def __init__(self, messages: List[BasePickUpMessage.BatchedMessage] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if messages is not None:
            attach = []
            for msg in messages:
                attach.append({
                    '@id': msg.msg_id,
                    'message': msg.message
                })
            self['messages~attach'] = attach

    @property
    def messages(self) -> List[BasePickUpMessage.BatchedMessage]:
        messages = []
        for attach in self.get('messages~attach', []):
            message = BasePickUpMessage.BatchedMessage(
                msg_id=attach.get('@id', None),
                message=attach.get('message', None)
            )
            messages.append(message)
        return messages


class PickUpNoop(BasePickUpMessage):
    NAME = 'noop'

    def __init__(self, delay_timeout: float = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if delay_timeout is not None:
            self['~timing'] = {'delay_milli': math.ceil(delay_timeout*1000)}

    @property
    def delay_timeout(self) -> Optional[float]:
        delay_milli = self.get('~timing', {}).get('delay_milli', None)
        if delay_milli is not None:
            return delay_milli / 1000
        else:
            return None


class PickUpProblemReport(AriesProblemReport, metaclass=RegisterMessage):
    DOC_URI = VALID_DOC_URI[0]
    PROTOCOL = BasePickUpMessage.PROTOCOL


class PickUpStateMachine:

    PROBLEM_CODE_TIMEOUT = 'timeout_occurred'
    PROBLEM_CODE_EMPTY = 'empty_queue'
    PROBLEM_CODE_INVALID_REQ = 'invalid_request'

    @dataclass
    class QueuedItem:
        item: BasePickUpMessage.BatchedMessage
        stamp: datetime.datetime = None

    def __init__(self, max_queue_size: int = None):
        self.__messages: OrderedDictAlias[str, PickUpStateMachine.QueuedItem] = OrderedDict()
        self.__max_queue_size = max_queue_size
        self.__filled = asyncio.Event()
        self.__ready_to_put = asyncio.Event()
        self.__ready_to_put.set()
        self.__last_added_time = None
        self.__message_count = 0

    @property
    def message_count(self) -> int:
        return self.__message_count

    async def put(self, message: Union[dict, str], msg_id: str = None):
        await self.__ready_to_put.wait()
        if isinstance(message, dict):
            msg_id = message.get('@id', None)
        elif isinstance(message, str):
            try:
                js = json.loads(message)
                msg_id = js.get('@id', None)
            except json.JSONDecodeError:
                msg_id = None
        msg_id = msg_id or uuid.uuid4().hex
        item = BasePickUpMessage.BatchedMessage(msg_id=msg_id, message=message)
        self.__messages[msg_id] = PickUpStateMachine.QueuedItem(item=item, stamp=datetime.datetime.utcnow())
        self.__messages.move_to_end(msg_id, last=True)
        self.__last_added_time = datetime.datetime.utcnow()
        self.__message_count += 1
        self.__filled.set()
        if self.__max_queue_size is not None:
            if self.__message_count < self.__max_queue_size:
                self.__ready_to_put.set()
            else:
                self.__ready_to_put.clear()

    async def process(self, request: BasePickUpMessage) -> BasePickUpMessage:
        if isinstance(request, PickUpStatusRequest):
            response = PickUpStatusResponse(
                message_count=self.__message_count,
                duration_limit=0,
                last_added_time=str(self.__last_added_time) if self.__last_added_time else None
            )
            self.__prepare_response(request=request, response=response)
            return response
        elif isinstance(request, PickUpBatchRequest):
            until_stamp = None
            if request.delay_timeout is not None and request.delay_timeout >= 0:
                until_stamp = datetime.datetime.now() + datetime.timedelta(seconds=request.delay_timeout)
            while request.batch_size > self.__message_count:
                if until_stamp is not None:
                    delta = until_stamp - datetime.datetime.now()
                    if delta.total_seconds() >= 0:
                        wait_timeout = delta.total_seconds()
                    else:
                        break
                else:
                    wait_timeout = None
                try:
                    await asyncio.wait_for(self.__filled.wait(), timeout=wait_timeout)
                except asyncio.TimeoutError:
                    break

            messages = []
            size_to_retrieve = min(request.batch_size, self.__message_count)
            msg_ids = list(self.__messages.keys())[:size_to_retrieve]
            for msg_id in msg_ids:
                queued = self.__messages[msg_id]
                messages.append(queued.item)
                del self.__messages[msg_id]
                self.__message_count -= 1
            response = PickUpBatchResponse(messages=messages)
            self.__prepare_response(request=request, response=response)
            return response
        elif isinstance(request, PickUpListRequest):
            messages = []
            for msg_id in request.message_ids:
                if msg_id in self.__messages.keys():
                    queued = self.__messages[msg_id]
                    messages.append(queued.item)
            response = PickUpListResponse(messages=messages)
            self.__prepare_response(request=request, response=response)
            return response
        elif isinstance(request, PickUpNoop):
            if request.delay_timeout is None and self.__message_count == 0:
                response = PickUpProblemReport(
                    problem_code=self.PROBLEM_CODE_EMPTY, explain='Message queue is empty'
                )
            else:
                batch = PickUpBatchRequest(batch_size=1, delay_timeout=request.delay_timeout)
                batched = await self.process(batch)
                assert isinstance(batched, PickUpBatchResponse)
                if batched.messages:
                    response = batched.messages[0].message
                else:
                    response = PickUpProblemReport(
                        problem_code=self.PROBLEM_CODE_TIMEOUT, explain='Message queue is empty, timeout occurred'
                    )
            self.__prepare_response(request=request, response=response)
            return response
        else:
            response = PickUpProblemReport(problem_code=self.PROBLEM_CODE_INVALID_REQ, explain='Unknown request type')
            self.__prepare_response(request=request, response=response)
            return response

    def __prepare_response(self, request: BasePickUpMessage, response: BasePickUpMessage):
        if request.return_route == 'thread':
            response['~thread'] = {'thid': request.id}
        if self.__message_count == 0:
            self.__filled.clear()
        if self.__max_queue_size is not None:
            if self.__message_count < self.__max_queue_size:
                self.__ready_to_put.set()
            else:
                self.__ready_to_put.clear()
