import logging
from typing import Union

import sirius_sdk


def info_p2p_event(p2p: Union[sirius_sdk.Pairwise, str], message: str, **context):
    extra = {}
    if isinstance(p2p, str):
        extra['did'] = p2p
    elif isinstance(p2p, sirius_sdk.Pairwise):
        extra['did'] = p2p.their.did
        extra['verkey'] = p2p.their.verkey
        extra['label'] = p2p.their.label
        extra['endpoint'] = p2p.their.endpoint
    else:
        return
    if context:
        extra.update(context)
    logging.info(message, extra=extra)
