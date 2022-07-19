import hashlib
import json
import logging
from urllib.parse import urljoin

import sirius_sdk
from sirius_sdk.encryption import pack_message
from sirius_sdk import Pairwise
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol.messages import ConnProtocolMessage

from app.settings import KEYPAIR, DID, MEDIATOR_SERVICE_TYPE, FCM_SERVICE_TYPE
from app.core.repo import Repo
from app.utils import async_build_ws_endpoint_addr, async_build_long_polling_addr
from app.core.redis import choice_server_address as choice_redis_server_address


def build_consistent_endpoint_uid(did: str) -> str:
    return hashlib.sha256(did.encode('utf-8')).hexdigest()


async def build_did_doc_extra(repo: Repo, their_did: str, their_verkey: str, group_id: str = None) -> (str, str, dict):
    """
    :return: endpoint addr, endpoint-uid, extra did_doc
    """
    ws_endpoint = await async_build_ws_endpoint_addr(repo.db)
    endpoint_uid = build_consistent_endpoint_uid(their_did)
    # Declare MediatorService endpoint via DIDDoc
    did_doc = ConnProtocolMessage.build_did_doc(did=DID, verkey=KEYPAIR[0], endpoint=ws_endpoint)
    did_doc_extra = {'service': did_doc['service']}
    mediator_service_endpoint = await async_build_ws_endpoint_addr(repo.db)
    mediator_service_endpoint = urljoin(mediator_service_endpoint, f'?endpoint={endpoint_uid}')
    if group_id is not None:
        mediator_service_endpoint += f'&group_id={group_id}'
    did_doc_extra['service'].append({
        "id": 'did:peer:' + DID + ";indy",
        "type": MEDIATOR_SERVICE_TYPE,
        "priority": 1,
        "recipientKeys": [],
        "serviceEndpoint": mediator_service_endpoint,
    })
    long_polling_mediator_service_endpoint = await async_build_long_polling_addr(repo.db)
    long_polling_mediator_service_endpoint = urljoin(long_polling_mediator_service_endpoint, f'?endpoint={endpoint_uid}')
    if group_id is not None:
        long_polling_mediator_service_endpoint += f'&group_id={group_id}'
    did_doc_extra['service'].append({
        "id": 'did:peer:' + DID + ";indy",
        "type": MEDIATOR_SERVICE_TYPE,
        "priority": 2,
        "recipientKeys": [],
        "serviceEndpoint": long_polling_mediator_service_endpoint,
    })

    # configure redis pubsub infrastructure for endpoint
    data = await repo.load_endpoint(endpoint_uid)
    need_to_update = False

    if data is not None:
        stored_verkey = data.get('verkey', None)
        if their_verkey != stored_verkey:
            need_to_update = True
        redis_pub_sub_to_store = data.get('redis_pub_sub', None)
    else:
        need_to_update = True
        redis_pub_sub_to_store = None

    if need_to_update:
        if redis_pub_sub_to_store is None:
            redis_server = await choice_redis_server_address()
            redis_pub_sub = f'{redis_server}/{endpoint_uid}'
        else:
            # don't update
            redis_pub_sub = None
        await repo.ensure_endpoint_exists(
            uid=endpoint_uid,
            redis_pub_sub=redis_pub_sub,
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
    exists_data = await repo.load_agent(p2p.their.did)
    if exists_data:
        stored_did = exists_data.get('did', None)
        stored_verkey = exists_data.get('verkey', None)
        stored_metadata = exists_data.get('metadata', None)
        stored_fcm_device_id = exists_data.get('fcm_device_id', None)
        need_update = (stored_did != p2p.their.did) or (stored_verkey != p2p.their.verkey) or (stored_fcm_device_id != fcm_device_id)
        if need_update:
            logging.debug('----------- Update Agent info ------------')
            logging.debug('Old data:')
            logging.debug(json.dumps(exists_data, indent=2, sort_keys=True))
            logging.debug('New data:')
            logging.debug(json.dumps(
                dict(did=p2p.their.did, verkey=p2p.their.verkey, metadata=p2p.metadata, fcm_device_id=fcm_device_id),
                indent=2, sort_keys=True))
            logging.debug('------------------------------------------')
    else:
        need_update = True
    if need_update:
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


def validate_verkey(verkey: str) -> bool:
    try:
        pack_message('test', to_verkeys=[verkey])
        return True
    except Exception as e:
        print('===================================')
        print(repr(e))
        print('===================================')
        return False


async def create_static_connection(repo: Repo, label: str, their_did: str, their_verkey: str, fcm_device_id: str = None) -> Pairwise:
    ws_endpoint, endpoint_uid, did_doc_extra = await build_did_doc_extra(
        repo=repo,
        their_did=their_did,
        their_verkey=their_verkey
    )
    their_endpoint = 'ws://'
    their_did_doc = ConnProtocolMessage.build_did_doc(did=their_did, verkey=their_verkey, endpoint=their_endpoint)
    if fcm_device_id:
        their_did_doc['service'].append({
            "id": 'did:peer:' + their_did + ";indy",
            "type": FCM_SERVICE_TYPE,
            "recipientKeys": [],
            "priority": 1,
            "serviceEndpoint": fcm_device_id,
        })
    my_did_doc = ConnProtocolMessage.build_did_doc(did=DID, verkey=KEYPAIR[0], endpoint=ws_endpoint)
    my_did_doc['service'] = did_doc_extra['service']

    await sirius_sdk.DID.store_their_did(their_did, their_verkey)

    me = Pairwise.Me(
        did=DID,
        verkey=KEYPAIR[0],
        did_doc=my_did_doc
    )
    their = Pairwise.Their(
        did=their_did,
        label=label,
        endpoint=their_endpoint,
        verkey=their_verkey,
        routing_keys=[],
        did_doc=their_did_doc
    )
    metadata = {
        'me': {
            'did': DID,
            'verkey': KEYPAIR[0],
            'did_doc': dict(my_did_doc)
        },
        'their': {
            'did': their_did,
            'verkey': their_verkey,
            'label': label,
            'endpoint': {
                'address': their_endpoint,
                'routing_keys': []
            },
            'did_doc': their_did_doc
        }
    }
    p2p = Pairwise(me=me, their=their, metadata=metadata)
    await sirius_sdk.PairwiseList.ensure_exists(p2p)
    return p2p


def build_protocol_topic(their_did: str, binding_id: str) -> str:
    return f'{their_did}/{binding_id}'


def parse_protocol_topic(topic: str) -> (str, str):
    parts = topic.split('/')
    if len(parts) == 2:
        their_did, binding_id = parts
    else:
        their_did, binding_id = None, topic
    return their_did, binding_id
