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
                if full_test:
                    test_game_id = "test1234-test-1234-test-test1234test"
                    asset_clicks = {
                        "BOMB": {"clicks": 0},
                        "CLOVER": {"clicks": 150},
                        "FREEZE": {"clicks": 0},
                        "HARRIS": {"clicks": 0},
                        "TRUMP": {"clicks": 300}
                    }
                    earned_points = {"BP": {"amount": 150 + 300 * 5}}
                    payload = await get_payload(payload_server_url, test_game_id, earned_points, asset_clicks)
                    return len(payload) == 684

                if response.status != 200 or (await response.json()).get("status") != "ok":
                    return False
                return True
        except (TimeoutError, ClientConnectorError):
            logger.debug(f"Try connect to payload server ({url}) failed...")
    return False

async def get_payload(payload_server_url: str, game_id: str, earned_points: dict, asset_clicks: dict) -> str | None:
    async with ClientSession() as session:
        payload_data = {"gameId": game_id, "earnedPoints": earned_points, "assetClicks": asset_clicks}
        async with session.post(url=f"{payload_server_url}/getPayload", json=payload_data) as response:
            data = await response.json()
            if response.status == 200 and data.get("payload"):
                return data.get("payload")
            logger.error(f"Payload Server Error: {data.get('error')}")
            raise KeyboardInterrupt
