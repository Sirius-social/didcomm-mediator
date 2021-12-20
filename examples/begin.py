import asyncio

import aiohttp
import sirius_sdk
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import MediateRequest

from helpers.common import HARDCODED_INVITATION, MY_SEED, pretty
from helpers.crypto import LocalCrypto, create_did_and_keys
from helpers.did import LocalDID
from helpers.coprotocols import WebSocketCoProtocol


async def run(my_did: str, my_verkey: str, my_secret: str):

    mediator_invitation = sirius_sdk.aries_rfc.Invitation(**HARDCODED_INVITATION)

    # Make connection to Mediator:
    #  - using websocket as duplex transport
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(
        url=HARDCODED_INVITATION['serviceEndpoint'], ssl=False
    )
    pretty(f"#1. Connected via websocket to {HARDCODED_INVITATION['serviceEndpoint']}")
    #  - and using mediator public key and self keys to init P2P connection
    coprotocol = WebSocketCoProtocol(
        ws=ws,
        my_keys=(my_verkey, my_secret),
        their_verkey=HARDCODED_INVITATION['recipientKeys'][0]
    )

    # Run P2P connection establishment according Aries-RFC0160
    # - RFC: https://github.com/hyperledger/aries-rfcs/tree/master/features/0160-connection-protocol
    # - recipient declare endpoint address as "ws://" that means communication is established over duplex channel
    #   see details: https://github.com/hyperledger/aries-rfcs/tree/main/features/0092-transport-return-route
    state_machine = sirius_sdk.aries_rfc.Invitee(
        me=sirius_sdk.Pairwise.Me(did=my_did, verkey=my_verkey),
        my_endpoint=sirius_sdk.Endpoint(address='ws://', routing_keys=[]),
        coprotocol=coprotocol
    )
    # Recipient DIDDoc contains Firebase device id inside service with type "FCMService"
    did_doc = sirius_sdk.aries_rfc.ConnRequest.build_did_doc(my_did, my_verkey, 'ws://')
    did_doc_extra = {'service': did_doc['service']}
    did_doc_extra['service'].append({
        "id": 'did:peer:' + my_did + ";indy",
        "type": 'FCMService',
        "recipientKeys": [],
        "priority": 1,
        "serviceEndpoint": 'firebase-device-id',
    })
    pretty('#2. My DIDDoc\n', did_doc)
    success, p2p = await state_machine.create_connection(
        invitation=mediator_invitation,
        my_label='Test-Client',
        did_doc=did_doc_extra
    )
    if success:
        pretty('#3. P2P successfully established')
        # Mediator should declare service  with type: "MediatorService" that has url to listen endpoint events
        mediator_did_doc = p2p.their.did_doc
        pretty('#4. Mediator DIDDoc\n', mediator_did_doc)
        # It's time to get Http endpoint
        mediate_request = MediateRequest()
        # Use same websocket connection
        success, mediate_grant = await coprotocol.switch(mediate_request)
        if success:
            # You may declare this endpoint in Invitations:
            # - https://github.com/hyperledger/aries-rfcs/tree/main/features/0160-connection-protocol#0-invitation-to-connect
            pretty('My Endpoint: ' + mediate_grant['endpoint'])
        # In the course of work, errors are possible.
        # The mediator will report them in the form of ProblemReport, let's create such a situation
        # try to get Endpoint without P2P

        # Uncomment lines below to emulate problem-report
        """
        alien_did, alien_verkey, alien_secret = create_did_and_keys()
        alien_coprotocol = WebSocketCoProtocol(
            ws=ws,
            my_keys=(alien_verkey, alien_secret),
            their_verkey=HARDCODED_INVITATION['recipientKeys'][0]
        )
        success, problem_report = await alien_coprotocol.switch(mediate_request)
        pretty('Problem report:\n', problem_report)
        """
    pretty('Bye!')


if __name__ == '__main__':
    # Create keys
    my_did_, my_verkey_, my_secret_ = create_did_and_keys(seed=MY_SEED)
    # We initialize the SDK, for simplicity we redefine Crypto and DID so that the SDK does not address agents
    sirius_sdk.init(crypto=LocalCrypto(my_verkey_, my_secret_), did=LocalDID())
    # RUN!!!
    asyncio.get_event_loop().run_until_complete(run(my_did_, my_verkey_, my_secret_))
