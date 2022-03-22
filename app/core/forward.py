import uuid
import json
from typing import Optional

from sirius_sdk.encryption import pack_message, b58_to_bytes

FORWARD = 'https://didcomm.org/routing/1.0/forward'
ENCODING = 'ascii'


def forward_wired(payload: bytes, their_vk: Optional[str], routing_keys: list) -> bytes:
    keys_map = {}
    for n in range(len(routing_keys) - 1, 0, -1):  # example: IF routing_keys = ['k1', 'k2', 'k3'] THEN n = [2,1]
        outer_key = routing_keys[n]
        inner_key = routing_keys[n - 1]
        keys_map[outer_key] = inner_key
    keys_map[routing_keys[0]] = their_vk

    for outer_key in routing_keys:
        inner_key = keys_map[outer_key]
        outer_key_bytes = b58_to_bytes(outer_key)
        forwarded = {
            '@id': uuid.uuid4().hex,
            '@type': FORWARD,
            'to': inner_key,
            'msg': json.loads(payload.decode(ENCODING))
        }
        payload = pack_message(json.dumps(forwarded), to_verkeys=[outer_key_bytes])

    return payload
