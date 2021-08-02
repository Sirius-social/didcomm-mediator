from app.settings import REDIS
from app.core.redis import AsyncRedisChannel


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


async def check_services() -> list:
    services = []
    for n, item in enumerate([('WebRoot', 'https://sdvsd'), ('Service endpoint', 'wss://sdvdsv')]):
        name, address = item
        item = {
            'id': n + 1,
            'name': name,
            'address': address,
            'success': True
        }
        services.append(item)
    return services