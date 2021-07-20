import asyncio
from typing import List

import aiohttp
import sirius_sdk
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import MediateRequest, \
    KeylistAddAction, KeylistRemoveAction, KeylistUpdate, KeylistQuery

from helpers.common import HARDCODED_INVITATION
from helpers.crypto import LocalCrypto, create_did_and_keys
from helpers.did import LocalDID
from helpers.coprotocols import WebSocketCoProtocol


async def clear_all_keys(co: WebSocketCoProtocol, endpoint: str, keys: List[str]):
    updates = [KeylistRemoveAction(recipient_key=key) for key in keys]
    update_request = KeylistUpdate(endpoint, updates=updates)
    success, updates_response = await co.switch(message=update_request)
    assert success
    assert all(record['result'] == 'success' for record in updates_response['updated'])


async def run(my_did: str, my_verkey: str, my_secret: str):

    mediator_invitation = sirius_sdk.aries_rfc.Invitation(**HARDCODED_INVITATION)

    # Подключаемся по вебсокету
    print('#1. Connecting to mediator')
    print('#1.1 Allocate websocket connection...')
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(
        url=HARDCODED_INVITATION['serviceEndpoint']
    )
    print('#1.2 Websocket connection successfully established')
    try:
        # Настраиваем транспорт, указываем открытый ключ партнера для туннелирования
        print('#2. Ensure P2P encrypted connection established')
        print('#2.1 Extract public key (verkey) from Mediator invitation')
        their_verkey = HARDCODED_INVITATION['recipientKeys'][0]
        coprotocol = WebSocketCoProtocol(ws=ws, my_keys=(my_verkey, my_secret), their_verkey=their_verkey)

        # Запускаем AriesRFC-0160 Invitee
        print('#2.2 Start connection protocol to establish P2P')
        state_machine = sirius_sdk.aries_rfc.Invitee(
            me=sirius_sdk.Pairwise.Me(did=my_did, verkey=my_verkey),
            my_endpoint=sirius_sdk.Endpoint(address='ws://', routing_keys=[]),
            coprotocol=coprotocol
        )
        success, p2p = await state_machine.create_connection(
            invitation=mediator_invitation,
            my_label='Test-Client',
        )
        if success:
            print('#3. Mediate request: check routing keys')
            success, mediate_grant = await coprotocol.switch(message=MediateRequest())
            if success:
                my_endpoint = mediate_grant['endpoint']
                print('\n')
                print('My Endpoint: ' + my_endpoint)
                print('My routing keys: ' + str(mediate_grant['routing_keys']))
                print('\n')
                if mediate_grant['routing_keys']:
                    print('#3.1 remove all routing keys')
                    await clear_all_keys(coprotocol, my_endpoint, mediate_grant['routing_keys'])

                print('#4 Update routing keys for endpoint')
                print('#4.1 Generate routing key')
                random_verkey, _ = sirius_sdk.encryption.create_keypair()
                random_verkey = sirius_sdk.encryption.bytes_to_b58(random_verkey)
                key_to_update = f'did:key:{random_verkey}'
                print('#4.2 Build update request command Aries-RFC 0211 https://github.com/hyperledger/aries-rfcs/tree/master/features/0211-route-coordination')
                route_update_keys = KeylistUpdate(
                    endpoint=my_endpoint,
                    updates=[
                        KeylistAddAction(recipient_key=key_to_update)
                    ]
                )
                success, update_keys_resp = await coprotocol.switch(message=route_update_keys)
                print('#4.3 Process keys update response')
                assert success
                print('#5 Clean all routing keys')
                await clear_all_keys(coprotocol, my_endpoint, keys=[key_to_update])
            else:
                raise RuntimeError('Error while requesting mediator to fetch endpoint address and routing keys')
        else:
            raise RuntimeError('Error while establish P2P connection with mediator')
    finally:
        await session.close()


if __name__ == '__main__':
    # Создаем ключи
    my_did_, my_verkey_, my_secret_ = create_did_and_keys(seed='0000000000000000000000000EXAMPLE')
    # Инициализируем SDK, для простоты переопределим Crypto и DID, чтобы SDK не обращался к агентам
    sirius_sdk.init(crypto=LocalCrypto(my_verkey_, my_secret_), did=LocalDID())
    # Запускаем тест
    asyncio.get_event_loop().run_until_complete(run(my_did_, my_verkey_, my_secret_))
