import asyncio

import aiohttp
import sirius_sdk
from sirius_sdk.agent.aries_rfc.feature_0211_mediator_coordination_protocol.messages import MediateRequest

from helpers.common import HARDCODED_INVITATION
from helpers.crypto import LocalCrypto, create_did_and_keys
from helpers.did import LocalDID
from helpers.coprotocols import WebSocketCoProtocol


async def listen_websocket(url: str):
    session = aiohttp.ClientSession()
    try:
        ws = await session.ws_connect(url)
    except Exception as e:
        raise
    try:
        print(f'Device: start listening websocket: {url}')
        while True:
            payload = await ws.receive_bytes()
            print('>>> Device received payload:')
            print('\t' + repr(payload))
            print('<<< -----------------------')
    finally:
        await session.close()


async def run(my_did: str, my_verkey: str, my_secret: str):

    url = 'ws://mediator.socialsirius.com:8000/ws?endpoint=e2afc79cc785801e4fff71ca0314bae8cf9959f37d05c7ca722721acc91530ab'
    await listen_websocket(url)

    mediator_invitation = sirius_sdk.aries_rfc.Invitation(**HARDCODED_INVITATION)

    # Подключаемся по вебсокету
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(
        url=HARDCODED_INVITATION['serviceEndpoint']
    )
    try:
        # Настраиваем транспорт, указываем открытый ключ партнера для туннелирования
        their_verkey = HARDCODED_INVITATION['recipientKeys'][0]
        coprotocol = WebSocketCoProtocol(ws=ws, my_keys=(my_verkey, my_secret), their_verkey=their_verkey)

        # Запускаем AriesRFC-0160 Invitee
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
            mediator_did_doc = p2p.their.did_doc
            mediator_service = [srv for srv in mediator_did_doc['service'] if srv['type'] == 'MediatorService'][0]
            # осталось узнать, какой endpoint для нас выделил медиатор
            mediate_request = MediateRequest()
            success, mediate_grant = await coprotocol.switch(mediate_request)
            if success:
                # Этот endpoint теперь везде можно использовать в Invitations
                print('My Http Endpoint: ' + mediate_grant['endpoint'])
                print('Websocket to pull events: ' + mediator_service['serviceEndpoint'])
                # Эмулируем в независимой нитке device
                device = asyncio.ensure_future(listen_websocket(url=mediator_service['serviceEndpoint']))
                try:
                    await asyncio.sleep(300)
                finally:
                    device.cancel()
    finally:
        await session.close()


if __name__ == '__main__':
    # Создаем ключи
    my_did_, my_verkey_, my_secret_ = create_did_and_keys(seed='0000000000000000000000000EXAMPLE')
    # Инициализируем SDK, для простоты переопределим Crypto и DID, чтобы SDK не обращался к агентам
    sirius_sdk.init(crypto=LocalCrypto(my_verkey_, my_secret_), did=LocalDID())
    # Запускаем тест
    asyncio.get_event_loop().run_until_complete(run(my_did_, my_verkey_, my_secret_))
