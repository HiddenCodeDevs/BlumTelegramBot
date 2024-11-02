from pyrogram import Client

from bot.config import settings
from bot.utils.logger import logger

async def register_sessions() -> None:

    if not settings.API_ID or not settings.API_HASH:
        raise ValueError("API_ID and API_HASH not found in the .env file.")

    session_name = input('\nEnter the session name (press Enter to exit): ')

    if not session_name:
        return None

    session = Client(
        name=session_name,
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        workdir="sessions/"
    )

    async with session:
        user_data = await session.get_me()

    logger.success(f'Session added successfully @{user_data.username} | {user_data.first_name} {user_data.last_name}')
