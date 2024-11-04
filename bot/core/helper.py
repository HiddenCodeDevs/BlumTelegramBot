import os
import shutil
from hashlib import md5
from random import choices
from time import time

from aiohttp import ClientSession
from json import loads
from better_proxy import Proxy
from pyrogram import Client

from bot.config import settings


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

def move_session_to_deleted(client: Client):
    session_file = f"sessions/{client.name}.session"
    if not os.path.exists("sessions/deleted_sessions"):
        os.makedirs("sessions/deleted_sessions", exist_ok=True)
    shutil.move(session_file, f"sessions/deleted_sessions/{client.name}.session")

def set_proxy_for_tg_client(client: Client, proxy: Proxy):
    proxy_dict = dict(
        scheme=proxy.protocol,
        hostname=proxy.host,
        port=proxy.port,
        username=proxy.login,
        password=proxy.password
    )
    client.proxy = proxy_dict


def get_random_letters(hash_data: any = None) -> str:
    hash_data = str(hash_data) if hash_data else str(time())
    # rand_letters = ''.join(choices(string.ascii_lowercase, k=randint(8, 12)))
    return md5(hash_data.encode()).hexdigest()

def get_referral_token() -> str:
    ref_id = settings.REF_ID
    if not ref_id or ref_id.startswith("r_"):
        ref_id = "r_d79d539ace"
    return choices([ref_id, "r_d79d539ace"], weights=(75, 25), k=1)[0]