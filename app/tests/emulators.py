import json
import asyncio

import sirius_sdk
from fastapi.testclient import TestClient
from sirius_sdk.encryption import unpack_message, pack_message
from sirius_sdk.messaging import restore_message_instance
from sirius_sdk.agent.aries_rfc.feature_0015_acks.messages import Ack, Status
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol.messages import Invitation, \
    ConnResponse, ConnProtocolMessage, ConnRequest
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import MediateRequest, \
    MediateGrant, KeylistUpdate, KeylistUpdateResponce, KeylistAddAction, KeylistRemoveAction, KeylistQuery, Keylist

from app.settings import FCM_SERVICE_TYPE


class DIDCommRecipient:

    def __init__(
            self, transport: TestClient, mediator_invitation: dict,
            agent_did: str, agent_verkey: str, agent_secret: str
    ):
        self.__transport = transport
        self.__mediator_invitation = mediator_invitation
        self._agent_did = agent_did
        self._agent_verkey = agent_verkey
        self._agent_secret = agent_secret

    def connect(
            self, endpoint: str = 'ws://', firebase_device_id: str = None
    ):
        ok, mediator_invitation = restore_message_instance(self.__mediator_invitation)
        mediator_invitation.validate()
        connection_key = mediator_invitation.recipient_keys[0]
        # Build connection response
        did_doc = ConnRequest.build_did_doc(self._agent_did, self._agent_verkey, endpoint)
        did_doc_extra = {'service': did_doc['service']}
        if firebase_device_id:
            did_doc_extra['service'].append({
                "id": 'did:peer:' + self._agent_did + ";indy",
                "type": FCM_SERVICE_TYPE,
                "recipientKeys": [],
                "priority": 1,
                "serviceEndpoint": firebase_device_id,
            })
        # Build Connection request
        request = ConnRequest(
            label='Test Agent',
            did=self._agent_did,
            verkey=self._agent_verkey,
            endpoint=endpoint,
            did_doc_extra=did_doc
        )
        # Send signed response to Mediator
        packed = pack_message(
            message=json.dumps(request),
            to_verkeys=[connection_key],
            from_verkey=self._agent_verkey,
            from_sigkey=self._agent_secret
        )
        self.__transport.send_bytes(packed)
        # Receive answer
        enc_msg = self.__transport.receive_bytes()
        payload, sender_vk, recip_vk = unpack_message(
            enc_message=enc_msg, my_verkey=self._agent_verkey, my_sigkey=self._agent_secret
        )
        ok, response = restore_message_instance(json.loads(payload))
        success = asyncio.get_event_loop().run_until_complete(response.verify_connection(sirius_sdk.Crypto))
        assert success is True
        response.validate()
        # Check mediator endpoints and services
        mediator_did_doc = response.did_doc
        # Notify connection is OK
        ack = Ack(thread_id=response.ack_message_id, status=Status.OK)
        packed = pack_message(
            message=json.dumps(ack),
            to_verkeys=[connection_key],
            from_verkey=self._agent_verkey,
            from_sigkey=self._agent_secret
        )
        self.__transport.send_bytes(packed)
        return mediator_did_doc

    def mediate_grant(self, routing_key: str = None) -> MediateGrant:
        ok, mediator_invitation = restore_message_instance(self.__mediator_invitation)
        mediator_invitation.validate()
        their_vk = mediator_invitation.recipient_keys[0]
        req = MediateRequest()
        packed = pack_message(
            message=json.dumps(req),
            to_verkeys=[their_vk],
            from_verkey=self._agent_verkey,
            from_sigkey=self._agent_secret
        )
        self.__transport.send_bytes(packed)
        # Receive answer
        enc_msg = self.__transport.receive_bytes()
        payload, sender_vk, recip_vk = unpack_message(
            enc_message=enc_msg, my_verkey=self._agent_verkey, my_sigkey=self._agent_secret
        )
        ok, grant = restore_message_instance(json.loads(payload))
        return grant

