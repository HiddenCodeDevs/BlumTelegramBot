import traceback
from asyncio import sleep, CancelledError
from aiohttp import ClientSession, ClientTimeout
from aiohttp.client_exceptions import ClientProxyConnectionError
from python_socks import ProxyError

from bot.utils.logger import logger

async def check_proxy(http_client: ClientSession) -> str | None:
    try:
        response = await http_client.get(url='https://api.ipify.org?format=json', timeout=ClientTimeout(5))
        data = await response.json()
        if data and data.get('ip'):
            return data.get('ip')
    except (ConnectionRefusedError, ClientProxyConnectionError, CancelledError):
        logger.trace(f"Proxy not available")
    except ProxyError as e:
        logger.error(f"The proxy type may be incorrect! Error: {type(e).__name__}: {e}")
    except Exception as e:
        logger.error(f"{traceback.format_exc()}")


async def wait_proxy(http_client: ClientSession, time_between_checks_sec: int = 5) -> str | None:
    while True:
        ip = await check_proxy(http_client)
        if ip:
            return ip
        logger.trace(f"Proxy not available. Sleep {time_between_checks_sec} sec...")
        await sleep(time_between_checks_sec)
