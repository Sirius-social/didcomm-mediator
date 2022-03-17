import asyncio

import sirius_sdk

from helpers.did import LocalDID
from helpers.common import HARDCODED_INVITATION
from helpers.crypto import LocalCrypto, create_did_and_keys
from helpers.mediator import establish_ws_connection_with_mediator
from helpers.coprotocols import WebSocketListener


async def run(my_did: str, my_verkey: str, my_secret: str):
    print("Hello, I am Alice agent")
    print("connecting to mediator...")
    mediator_session, mediator_endpoint, ws_endpoint = await establish_ws_connection_with_mediator(
        mediator_invitation=HARDCODED_INVITATION,
        my_did=my_did, my_vk=my_verkey, my_sk=my_secret
    )
    # Generating invitation for Bob...
    connection_key = await sirius_sdk.Crypto.create_key()
    alice_invitation = sirius_sdk.aries_rfc.Invitation(
        label='Alice',
        recipient_keys=[connection_key],  # Any pub key from your crypto-box
        endpoint=mediator_endpoint
    )
    print('Paste this invitation to Bob console...')
    print('_______________________________________________')
    print('' + alice_invitation.invitation_url)
    print('_______________________________________________')
    print('Wait for Bob response...')
    listener = WebSocketListener(ws_endpoint)
    while True:
        msg, sender_vk, recip_vk = await listener.get_one()


if __name__ == '__main__':
    # Create keys
    my_did_, my_verkey_, my_secret_ = create_did_and_keys(seed='000000000000000000000000000ALICE')
    # We initialize the SDK, for simplicity we redefine Crypto and DID so that the SDK does not address agents
    # You may override this code block with Aries-Askar wrappers
    sirius_sdk.init(crypto=LocalCrypto(my_verkey_, my_secret_), did=LocalDID())
    # RUN!!!
    asyncio.get_event_loop().run_until_complete(run(my_did_, my_verkey_, my_secret_))
