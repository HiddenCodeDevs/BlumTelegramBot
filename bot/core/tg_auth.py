from urllib.parse import unquote

from pyrogram import Client
from pyrogram.errors import (
    Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan,
    AuthKeyDuplicated, SessionExpired, SessionRevoked
)
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName

from bot.core.helper import get_referral_token
from bot.exceptions import TelegramInvalidSessionException, TelegramProxyError
from bot.utils.logger import SessionLogger


async def get_tg_web_data(client: Client, log: SessionLogger) -> str:
    try:
        if not client.is_connected:
            await client.connect()
        acc = await client.get_me()
        log.trace(f"TG Account Login: {acc.username} ({acc.first_name}) {acc.last_name})")

        peer = await client.resolve_peer('BlumCryptoBot')
        web_view = await client.invoke(RequestAppWebView(
            peer=peer,
            app=InputBotAppShortName(bot_id=peer, short_name="app"),
            platform='android',
            write_allowed=True,
            start_param=get_referral_token()
        ))
        data = unquote(string=web_view.url.split('#tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])
        return data

    except (Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan, AuthKeyDuplicated,
            SessionExpired, SessionRevoked):
        raise TelegramInvalidSessionException(f"Telegram session is invalid. Client: {client.name}")
    except AttributeError as e:
        raise TelegramProxyError(e)
    finally:
        if client.is_connected:
            await client.disconnect()