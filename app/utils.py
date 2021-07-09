from urllib.parse import urljoin

import sirius_sdk

from app.settings import WEBROOT, MEDIATOR_LABEL, KEYPAIR


def build_ws_endpoint_addr() -> str:
    mediator_endpoint = WEBROOT
    if mediator_endpoint.startswith('https://'):
        mediator_endpoint = mediator_endpoint.replace('https://', 'wss://')
    elif mediator_endpoint.startswith('http://'):
        mediator_endpoint = mediator_endpoint.replace('http://', 'ws://')
    else:
        raise RuntimeError('Invalid WEBROOT url')
    return mediator_endpoint


def build_invitation(id_: str = None) -> dict:

    return sirius_sdk.aries_rfc.Invitation(
        id_=id_,
        label=MEDIATOR_LABEL,
        recipient_keys=[KEYPAIR[0]],
        endpoint=build_ws_endpoint_addr(),
        routing_keys=[]
    )
