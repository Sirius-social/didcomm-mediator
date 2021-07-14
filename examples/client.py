import asyncio

import aiohttp
import sirius_sdk

from coprotocols import WebSocketCoProtocol


HARDCODED_INVITATION = {
    "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/invitation",
    "@id": "309c526d-0b27-47e6-a1ec-8b16bb3fd3c7",
    "label": "Mediator",
    "recipientKeys": ["DjgWN49cXQ6M6JayBkRCwFsywNhomn8gdAXHJ4bb98im"],
    "serviceEndpoint": "ws://mediator.socialsirius.com:8000/ws",
    "routingKeys": []
}


async def run():
    seed = b'0000000000000000000000000EXAMPLE'
    v, s = sirius_sdk.encryption.create_keypair(seed)
    my_verkey = sirius_sdk.encryption.bytes_to_b58(v)
    my_secret = sirius_sdk.encryption.bytes_to_b58(s)
    my_did = sirius_sdk.encryption.bytes_to_b58(sirius_sdk.encryption.did_from_verkey(v))

    session = aiohttp.ClientSession()
    ws = await session.ws_connect(
        url='http://localhost:8000/ws'  # HARDCODED_INVITATION['serviceEndpoint']
    )
    print('#')


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(run())