import json as json_lib


MY_SEED = '0000000000000000000000000EXAMPLE'

HARDCODED_INVITATION = {
    "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/invitation",
    "@id": "309c526d-0b27-47e6-a1ec-8b16bb3fd3c7",
    "label": "Mediator",
    "recipientKeys": ["DjgWN49cXQ6M6JayBkRCwFsywNhomn8gdAXHJ4bb98im"],
    "serviceEndpoint": "wss://mediator.socialsirius.com/ws",
    "routingKeys": []
}


def pretty(msg: str, json: dict = None):
    if json:
        msg = msg + json_lib.dumps(json, indent=2, sort_keys=True)
    print('\n*******************************************************')
    print('\t' + msg)
    print('*******************************************************')
