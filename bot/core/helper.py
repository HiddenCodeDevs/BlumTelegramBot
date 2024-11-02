from aiohttp import ClientSession
from json import loads
from better_proxy import Proxy
from pyrogram import Client

def format_duration(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60
    return f"{int(hours)}h:{int(minutes)}m:{int(remaining_seconds)}s"

async def get_blum_database() -> dict | None:
    url = 'https://raw.githubusercontent.com/zuydd/database/main/blum.json'
    async with ClientSession() as session:
        request = await session.get(url=url, headers={"Accept": "application/json"})
        if request.status == 200:
            body = await request.text()
            return loads(body)

def set_proxy_for_tg_client(client: Client, proxy):
    if proxy:
        proxy = Proxy.from_str(proxy)
        proxy_dict = dict(
            scheme=proxy.protocol,
            hostname=proxy.host,
            port=proxy.port,
            username=proxy.login,
            password=proxy.password
        )
    else:
        proxy_dict = None
    client.proxy = proxy_dict
