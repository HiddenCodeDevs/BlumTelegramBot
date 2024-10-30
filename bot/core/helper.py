from aiohttp import ClientSession
from json import loads

async def get_blum_database() -> dict | None:
    url = 'https://raw.githubusercontent.com/zuydd/database/main/blum.json'
    async with ClientSession() as session:
        request = await session.get(url=url, headers={"Accept": "application/json"})
        if request.status == 200:
            body = await request.text()
            return loads(body)