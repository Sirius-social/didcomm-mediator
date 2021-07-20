import asyncio
import json

import aiohttp
import sirius_sdk
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import MediateRequest

from helpers.common import HARDCODED_INVITATION
from helpers.crypto import LocalCrypto, create_did_and_keys
from helpers.did import LocalDID
from helpers.fixtures import SAMPLE_PACKED_MSG
from helpers.coprotocols import WebSocketCoProtocol


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
            pass
    finally:
        await session.close()


if __name__ == '__main__':
    # Создаем ключи
    my_did_, my_verkey_, my_secret_ = create_did_and_keys(seed='0000000000000000000000000EXAMPLE')
    # Инициализируем SDK, для простоты переопределим Crypto и DID, чтобы SDK не обращался к агентам
    sirius_sdk.init(crypto=LocalCrypto(my_verkey_, my_secret_), did=LocalDID())
    # Запускаем тест
    asyncio.get_event_loop().run_until_complete(run(my_did_, my_verkey_, my_secret_))
