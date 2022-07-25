from typing import Optional, Union, List


THREAD_DECORATOR = '~thread'
PLEASE_ACK_DECORATOR = '~please_ack'
TRANSPORT_DECORATOR = '~transport'


def get_ack_message_id(message: dict) -> Optional[str]:
    return message.get(PLEASE_ACK_DECORATOR, {}).get('message_id', None)


def set_ack_message_id(message: dict, msg_id: str = None):
    if msg_id is None:
        msg_id = message.get('@id', None)
    if msg_id is not None:
        message[PLEASE_ACK_DECORATOR] = {'message_id': msg_id}


def get_thread_id(message: dict) -> Optional[Union[str, List[str]]]:
    return message.get(THREAD_DECORATOR, {}).get('thid', None)


def get_parent_thread_id(message: dict) -> Optional[str]:
    return message.get(THREAD_DECORATOR, {}).get('pthid', None)


def set_thread_id(message: dict, thid: Union[str, List[str]]):
    thread_decorator = message.get(THREAD_DECORATOR, {})
    thread_decorator['thid'] = thid
    message[THREAD_DECORATOR] = thread_decorator


def set_parent_thread_id(message: dict, thid: str):
    thread_decorator = message.get(THREAD_DECORATOR, {})
    thread_decorator['pthid'] = thid
    message[THREAD_DECORATOR] = thread_decorator


def get_return_route(message: dict) -> Optional[str]:
    return message.get(TRANSPORT_DECORATOR, {}).get('return_route', None)


def set_return_route(message: dict, value: str):
    transport_decorator = message.get(TRANSPORT_DECORATOR, {})
    transport_decorator['return_route'] = value
    message[TRANSPORT_DECORATOR] = value
