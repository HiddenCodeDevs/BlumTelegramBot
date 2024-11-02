from aiohttp import ClientSession, ClientConnectorError
from asyncio.exceptions import TimeoutError
from bot.utils.logger import logger

async def check_payload_server(payload_server_url: str, full_test: bool = False) -> bool:
    url = f"{payload_server_url}/status"

    if full_test and "https://" in payload_server_url and ("localhost:" in payload_server_url or "127.0.0.1:" in payload_server_url) :
        logger.warning("Are you sure you specified the correct protocol? "
                       "On local machines, <r>https</r> is usually not used!")

    async with ClientSession() as session:
        try:
            async with session.get(url, timeout=3) as response:
                if response.status == 200 and (await response.json()).get("status") == "ok" and not full_test:
                    return True
                if full_test:
                    test_game_id = "ad7cd4cd-29d1-4548-89a3-91301996ef31"
                    payload = await get_payload(payload_server_url, test_game_id, 150)
                    if len(payload) == 684:
                        return True
                return False
        except (TimeoutError, ClientConnectorError):
            pass
    return False

async def get_payload(payload_server_url: str, game_id: str, blum_points: int | str) -> str | None:
    async with ClientSession() as session:
        data = {
            "gameId": game_id,
            "earnedAssets": {
                "CLOVER": {
                    "amount": str(blum_points)
                }
            }
        }

        async with session.post(url=f"{payload_server_url}/getPayload", json=data) as response:
            data = await response.json()
            if response.status == 200 and data.get("payload"):
                return data.get("payload")
            raise Exception(f"Payload Server Error: {data.get('error')}")
