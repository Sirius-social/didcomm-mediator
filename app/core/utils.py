import logging
from typing import Union

import sirius_sdk


def info_p2p_event(p2p: Union[sirius_sdk.Pairwise, str], message: str, **context):
    record = {
        'message': message
    }
    if isinstance(p2p, str):
        record['did'] = p2p
    elif isinstance(p2p, sirius_sdk.Pairwise):
        record['did'] = p2p.their.did
        record['verkey'] = p2p.their.verkey
        record['label'] = p2p.their.label
        record['endpoint'] = p2p.their.endpoint
    else:
        return
    if context:
        record.update(context)
    logging.info(record)
