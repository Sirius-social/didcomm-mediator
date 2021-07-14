import asyncio

import aiohttp
import sirius_sdk
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import MediateRequest

from crypto import LocalCrypto
from did import LocalDID
from coprotocols import WebSocketCoProtocol


HARDCODED_INVITATION = {
    "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/invitation",
    "@id": "309c526d-0b27-47e6-a1ec-8b16bb3fd3c7",
    "label": "Mediator",
    "recipientKeys": ["DjgWN49cXQ6M6JayBkRCwFsywNhomn8gdAXHJ4bb98im"],
    "serviceEndpoint": "ws://mediator.socialsirius.com:8000/ws",
    "routingKeys": []
}


def create_did_and_keys(seed: str = None) -> (str, str, str):
    """
    :param seed: for const seed will be generated const did, verkey, secret
    :return: did, verkey, secret
    """

    if seed:
        seed = seed.encode()
    v, s = sirius_sdk.encryption.create_keypair(seed)
    verkey_ = sirius_sdk.encryption.bytes_to_b58(v)
    secret_ = sirius_sdk.encryption.bytes_to_b58(s)
    did_ = sirius_sdk.encryption.bytes_to_b58(sirius_sdk.encryption.did_from_verkey(v))
    return did_, verkey_, secret_


async def run(my_did: str, my_verkey: str, my_secret: str):

    mediator_invitation = sirius_sdk.aries_rfc.Invitation(**HARDCODED_INVITATION)

    # Подключаемся по вебсокету
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(
        url=HARDCODED_INVITATION['serviceEndpoint']
    )

    # Настраиваем транспорт, указываем открытый ключ партнера для туннелирования
    their_verkey = HARDCODED_INVITATION['recipientKeys'][0]
    coprotocol = WebSocketCoProtocol(ws=ws, my_keys=(my_verkey, my_secret), their_verkey=their_verkey)

    # Запускаем AriesRFC-0160 Invitee
    state_machine = sirius_sdk.aries_rfc.Invitee(
        me=sirius_sdk.Pairwise.Me(did=my_did, verkey=my_verkey),
        my_endpoint=sirius_sdk.Endpoint(address='ws://', routing_keys=[]),
        coprotocol=coprotocol
    )
    # Укажем в DIDDoc что нам можно осуществлять доставку по Firebase Cloud messaging
    did_doc = sirius_sdk.aries_rfc.ConnRequest.build_did_doc(my_did, my_verkey, 'ws://')
    did_doc_extra = {'service': did_doc['service']}
    did_doc_extra['service'].append({
        "id": 'did:peer:' + my_did + ";indy",
        "type": 'FCMService',
        "recipientKeys": [],
        "priority": 1,
        "serviceEndpoint": 'firebase-device-id',
    })
    success, p2p = await state_machine.create_connection(
        invitation=mediator_invitation,
        my_label='Test-Client',
        did_doc=did_doc_extra
    )
    if success:
        print('P2P successfully established')
        # медиатор должен был объявить сервис прослушивания событий Endpoint по WebSocket
        mediator_did_doc = p2p.their.did_doc
        mediator_service = [srv for srv in mediator_did_doc['service'] if srv['type'] == 'MediatorService'][0]
        # осталось узнать, какой endpoint для нас выделил медиатор
        mediate_request = MediateRequest()
        # используем тот же вебсокет
        success, mediate_grant = await coprotocol.switch(mediate_request)
        if success:
            # Этот endpoint теперь везде можно использовать в Invitations
            print('My Endpoint: ' + mediate_grant['endpoint'])
        # В ходе работы возможны ошибки. Медиатор сообщит о них в виде ProblemReport, создадим такую ситуацию
        # попытаемся получить Endpoint не имея P2P
        alien_did, alien_verkey, alien_secret = create_did_and_keys()
        alien_coprotocol = WebSocketCoProtocol(ws=ws, my_keys=(alien_verkey, alien_secret), their_verkey=their_verkey)
        print('#1')
        success, report = await alien_coprotocol.switch(mediate_request)
        print('#2')
    print('#')


if __name__ == '__main__':
    # Создаем ключи
    my_did, my_verkey, my_secret = create_did_and_keys(seed='0000000000000000000000000EXAMPLE')
    # Инициализируем SDK, для простоты переопределим Crypto и DID, чтобы SDK не обращался к агентам
    sirius_sdk.init(crypto=LocalCrypto(my_verkey, my_secret), did=LocalDID())
    # Запускаем тест
    asyncio.get_event_loop().run_until_complete(run(my_did, my_verkey, my_secret))
