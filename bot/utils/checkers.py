from aiohttp import ClientSession, ClientTimeout

async def check_proxy(http_client: ClientSession) -> None:
    response = await http_client.get(url='https://api.ipify.org?format=json', timeout=ClientTimeout(5))
    ip = (await response.json()).get('ip')
    return ip
