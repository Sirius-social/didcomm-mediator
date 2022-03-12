import asyncio

import aiohttp
import sirius_sdk

from helpers.common import HARDCODED_INVITATION, MY_SEED, pretty
from helpers.crypto import LocalCrypto, create_did_and_keys
from helpers.did import LocalDID
from helpers.coprotocols import WebSocketCoProtocol


async def run(my_did: str, my_verkey: str, my_secret: str):
    # Check we have active P2P connection to Mediator
    mediator = {
        'endpoint': HARDCODED_INVITATION['serviceEndpoint'],
        'verkey': HARDCODED_INVITATION['recipientKeys'][0]
    }
    pretty('#1. Mediator:\n', mediator)
    my = {
        'verkey': my_verkey,
        'secret': my_secret
    }
    pretty('#2. My:\n', my)
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(url=mediator['endpoint'], ssl=False)

    try:
        coprotocol = WebSocketCoProtocol(ws=ws, my_keys=(my['verkey'], my['secret']), their_verkey=mediator['verkey'])
        # RFC: https://github.com/hyperledger/aries-rfcs/tree/master/features/0048-trust-ping
        ping = sirius_sdk.aries_rfc.Ping(
            comment='I want check P2P connection',
            response_requested=True
        )

        pretty('Send ping:\n', ping)
        success, pong = await coprotocol.switch(message=ping)
        assert success is True

        pretty('Received pong:\n', pong)
    finally:
        await session.close()


if __name__ == '__main__':
    # Create keys
    my_did_, my_verkey_, my_secret_ = create_did_and_keys(seed=MY_SEED)
    # We initialize the SDK, for simplicity we redefine Crypto and DID so that the SDK does not address agents
    sirius_sdk.init(crypto=LocalCrypto(my_verkey_, my_secret_), did=LocalDID())
    # RUN!!!
    asyncio.get_event_loop().run_until_complete(run(my_did_, my_verkey_, my_secret_))
