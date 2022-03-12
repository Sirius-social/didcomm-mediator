import asyncio
import json

import aiohttp
import sirius_sdk
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import MediateRequest

from helpers.common import HARDCODED_INVITATION, MY_SEED, pretty
from helpers.crypto import LocalCrypto, create_did_and_keys
from helpers.did import LocalDID
from helpers.fixtures import SAMPLE_PACKED_MSG
from helpers.coprotocols import WebSocketCoProtocol


async def listen_websocket(url: str):
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(url, ssl=False)
    try:
        print(f'Device: start listening websocket: {url}')
        while True:
            payload = await ws.receive_json()
            print('>>> Device received:')
            print(json.dumps(payload, indent=2, sort_keys=True))
            print('<<< -----------------------')
    finally:
        await session.close()
        print(f'Device: stop listen websocket')


async def run(my_did: str, my_verkey: str, my_secret: str):

    mediator_invitation = sirius_sdk.aries_rfc.Invitation(**HARDCODED_INVITATION)

    # Make connection to Mediator using websocket as duplex transport
    print('#1. Connecting to mediator')
    print('#1.1 Allocate websocket connection...')
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(
        url=HARDCODED_INVITATION['serviceEndpoint'], ssl=False
    )
    print('#1.2 Websocket connection successfully established')
    try:
        # We set up the transport, specify the partner's public key for tunneling
        pretty('#2. Ensure P2P encrypted connection established')
        pretty('#2.1 Extract public key (verkey) from Mediator invitation')
        their_verkey = HARDCODED_INVITATION['recipientKeys'][0]
        coprotocol = WebSocketCoProtocol(ws=ws, my_keys=(my_verkey, my_secret), their_verkey=their_verkey)

        # Launching AriesRFC-0160 Invitee
        pretty('#2.2 Start connection protocol to establish P2P')
        state_machine = sirius_sdk.aries_rfc.Invitee(
            me=sirius_sdk.Pairwise.Me(did=my_did, verkey=my_verkey),
            my_endpoint=sirius_sdk.Endpoint(address='ws://', routing_keys=[]),
            coprotocol=coprotocol
        )
        success, p2p = await state_machine.create_connection(
            invitation=mediator_invitation,
            my_label='Test-Client',
        )
        if success:
            pretty('#3. P2P with mediator service was successfully established')
            mediator_did_doc = p2p.their.did_doc
            mediator_service = [srv for srv in mediator_did_doc['service'] if srv['type'] == 'MediatorService'][0]
            # it remains to find out which endpoint the mediator has selected for us
            mediate_request = MediateRequest()
            pretty('#3.1 Allocate endpoint')
            success, mediate_grant = await coprotocol.switch(mediate_request)
            if success:
                # This endpoint can now be used everywhere in Invitations.
                pretty('#3.2 Mediator endpoints...')
                pretty('My Http Endpoint: ' + mediate_grant['endpoint'])
                pretty('My pulling address: ' + mediator_service['serviceEndpoint'])
                # We emulate device in an independent thread
                pretty('#4. Send binary data to device via allocated endpoint')
                device = asyncio.ensure_future(listen_websocket(url=mediator_service['serviceEndpoint']))
                try:
                    # give some time for server to accept connection
                    await asyncio.sleep(3)
                    pretty('#4.1 Send binary data to endpoint')
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                                url=mediate_grant['endpoint'],
                                data=SAMPLE_PACKED_MSG,
                                headers={'Content-Type': 'application/ssi-agent-wire'}
                        ) as resp:
                            pretty(f'#4.2 Response status code: {resp.status}')
                finally:
                    device.cancel()
    finally:
        await session.close()


if __name__ == '__main__':
    # Create keys
    my_did_, my_verkey_, my_secret_ = create_did_and_keys(seed=MY_SEED)
    # We initialize the SDK, for simplicity we redefine Crypto and DID so that the SDK does not address agents
    sirius_sdk.init(crypto=LocalCrypto(my_verkey_, my_secret_), did=LocalDID())
    # RUN!!!
    asyncio.get_event_loop().run_until_complete(run(my_did_, my_verkey_, my_secret_))
