import hashlib
from urllib.parse import urljoin

from sirius_sdk import Pairwise
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol.messages import ConnProtocolMessage

from app.settings import KEYPAIR, DID, MEDIATOR_SERVICE_TYPE, FCM_SERVICE_TYPE
from app.core.repo import Repo
from app.utils import async_build_ws_endpoint_addr
from app.core.redis import choice_server_address as choice_redis_server_address


async def build_did_doc_extra(repo: Repo, their_did: str, their_verkey: str) -> (str, str, dict):
    """
    :return: endpoint addr, endpoint-uid, extra did_doc
    """
    ws_endpoint = await async_build_ws_endpoint_addr(repo.db)
    endpoint_uid = hashlib.sha256(their_did.encode('utf-8')).hexdigest()
    # Declare MediatorService endpoint via DIDDoc
    did_doc = ConnProtocolMessage.build_did_doc(did=DID, verkey=KEYPAIR[0], endpoint=ws_endpoint)
    did_doc_extra = {'service': did_doc['service']}
    mediator_service_endpoint = await async_build_ws_endpoint_addr(repo.db)
    mediator_service_endpoint = urljoin(mediator_service_endpoint, f'?endpoint={endpoint_uid}')
    did_doc_extra['service'].append({
        "id": 'did:peer:' + DID + ";indy",
        "type": MEDIATOR_SERVICE_TYPE,
        "recipientKeys": [],
        "serviceEndpoint": mediator_service_endpoint,
    })
    # configure redis pubsub infrastructure for endpoint
    redis_server = await choice_redis_server_address()
    await repo.ensure_endpoint_exists(
        uid=endpoint_uid,
        redis_pub_sub=f'{redis_server}/{endpoint_uid}',
        verkey=their_verkey
    )
    return ws_endpoint, endpoint_uid, did_doc_extra


async def post_create_pairwise(repo: Repo, p2p: Pairwise, endpoint_uid: str):
    """
    :return: endpoint addr, endpoint-uid, extra did_doc
    """
    # Try to extract firebase device_id
    fcm_device_id = None
    if p2p.their.did_doc:
        their_services = p2p.their.did_doc.get('service', [])
        for service in their_services:
            if service['type'] == FCM_SERVICE_TYPE:
                fcm_device_id = service['serviceEndpoint']
                break
    await repo.ensure_agent_exists(
        did=p2p.their.did, verkey=p2p.their.verkey, metadata=p2p.metadata, fcm_device_id=fcm_device_id
    )
    agent = await repo.load_agent(did=p2p.their.did)
    await repo.ensure_endpoint_exists(
        uid=endpoint_uid,
        agent_id=agent['id'],
        verkey=p2p.their.verkey,
        fcm_device_id=fcm_device_id
    )
