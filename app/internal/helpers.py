import aiohttp
from databases import Database

from app.settings import REDIS
from app.utils import async_build_ws_endpoint_addr
from app.core.redis import AsyncRedisChannel
from app.core.singletons import GlobalMemcachedClient
from app.core.global_config import GlobalConfig


async def check_redis() -> list:
    results = []
    for n, address in enumerate(REDIS):
        address = f'redis://{address}'
        item = {
            'id': n+1,
            'address': address,
            'success': await AsyncRedisChannel.check_address(address)
        }
        results.append(item)
    return results


async def check_url(url: str) -> bool:
    try:
        if url.startswith('http'):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    return True
        elif url.startswith('ws'):
            session = aiohttp.ClientSession()
            await session.ws_connect(url)
            return True
        else:
            return False
    except Exception as e:
        print('=================== CHECK URL ===================')
        print(repr(e))
        print('=================================================')
        return False


async def check_services(db: Database) -> list:
    cfg = GlobalConfig(db, GlobalMemcachedClient.get())
    webroot = await cfg.get_webroot()
    ws_endpoint = await async_build_ws_endpoint_addr(db)
    services = []
    for n, item in enumerate([('WebRoot', webroot), ('Service endpoint', ws_endpoint)]):
        name, url = item
        success = await check_url(url)
        comment = 'reachable' if success else 'unreachable'
        item = {
            'id': n + 1,
            'name': name,
            'address': url,
            'success': success,
            'comment': comment
        }
        services.append(item)
    return services
