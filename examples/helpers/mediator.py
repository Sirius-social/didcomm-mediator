import aiohttp

import sirius_sdk
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import MediateRequest

from .coprotocols import WebSocketCoProtocol


async def establish_ws_connection_with_mediator(
        mediator_invitation: dict, my_did: str, my_vk: str, my_sk: str,
        firebase_device_id: str = None
) -> (WebSocketCoProtocol, str, aiohttp.ClientWebSocketResponse):
    """
    Establish connection with mediator

    :param mediator_invitation: invitation from didcomm-mediator admin
    :param my_did: recipient DID
    :param my_vk: recipient VK
    :param my_sk: recipient Secret Key
    :param firebase_device_id: (optional) - firebase device ID
    :return: Service-connection, endpoint, websocket to listen income packed messages
    """
    invitation = sirius_sdk.aries_rfc.Invitation(**mediator_invitation)
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(url=invitation.endpoint, ssl=False)
    connection = WebSocketCoProtocol(
        ws=ws,
        my_keys=(my_vk, my_sk),
        their_verkey=invitation.recipient_keys[0] if invitation.recipient_keys else []
    )
    state_machine = sirius_sdk.aries_rfc.Invitee(
        me=sirius_sdk.Pairwise.Me(did=my_did, verkey=my_vk),
        my_endpoint=sirius_sdk.Endpoint(address='ws://', routing_keys=[]),
        coprotocol=connection
    )
    did_doc = sirius_sdk.aries_rfc.ConnRequest.build_did_doc(my_did, my_vk, 'ws://')
    did_doc_extra = {'service': did_doc['service']}
    if firebase_device_id:
        did_doc_extra['service'].append({
            "id": 'did:peer:' + my_did + ";indy",
            "type": 'FCMService',
            "recipientKeys": [],
            "priority": 1,
            "serviceEndpoint": 'firebase-device-id',
        })
    success, p2p = await state_machine.create_connection(
        invitation=invitation,
        my_label='Test-Client',
        did_doc=did_doc_extra
    )
    if success:
        mediate_request = MediateRequest()
        # Use same websocket connection
        success, mediate_grant = await connection.switch(mediate_request)
        if success:
            endpoint = mediate_grant['endpoint']
            mediator_did_doc = p2p.their.did_doc
            mediator_service = [srv for srv in mediator_did_doc['service'] if srv['type'] == 'MediatorService'][0]
            ws = await session.ws_connect(mediator_service['serviceEndpoint'], ssl=False)
            return connection, endpoint, ws
        else:
            raise RuntimeError('Error while allocate endpoint')
    else:
        raise RuntimeError(state_machine.problem_report)
