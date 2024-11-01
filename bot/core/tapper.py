import asyncio
import os
from random import randint, choices, uniform
import shutil
import string
from urllib.parse import unquote

from time import time

from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from pyrogram import Client
from pyrogram.errors import (
    Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan,
    AuthKeyDuplicated, SessionExpired, SessionRevoked
)
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName


from bot.config import settings
from bot.core.agents import check_user_agent
from bot.core.api import BlumApi
from bot.core.headers import headers as default_headers
from bot.core.helper import get_blum_database, set_proxy_for_tg_client, format_duration
from bot.exceptions import InvalidSession
from bot.utils.payload import check_payload_server, get_payload
from bot.utils.logger import logger, SessionLogger
from bot.utils.checkers import check_proxy

SLEEP_SEC_BEFORE_ITERATIONS = 60 * 60 * 2

class Tapper:
    user_url = "https://user-domain.blum.codes"
    gateway_url = "https://gateway.blum.codes"
    wallet_url = "https://wallet-domain.blum.codes"
    subscription_url = "https://subscription.blum.codes"

    username: str
    play_passes: int
    farming_data: dict | None
    _log: SessionLogger = None
    _session: CloudflareScraper = None

    def __init__(self, tg_client: Client, loop):
        self.tg_client = tg_client
        self._log = SessionLogger(self.tg_client.name)
        self._api = BlumApi(self._log)
        self.refresh_token = ""
        self.login_time = 0
        self._loop = loop

    def __del__(self):
        if self._session:
            self._loop.create_task(self._session.close())

    def set_tokens(self, access_token, refresh_token):
        if access_token and refresh_token:
            self._session.headers["Authorization"] = f"Bearer {access_token}"
            self.refresh_token = refresh_token
            self.login_time = time()
        else:
            self._log.error('Can`t get new token, trying again')

    async def update_access_token(self):
        access_token, refresh_token = await self._api.get_new_auth_tokens(self.refresh_token)
        self.set_tokens(access_token, refresh_token)
        self.login_time = time()

    async def auth(self, proxy):
        init_data = await self.get_tg_web_data(proxy=proxy)
        self._log.debug("Got init data for auth.")
        if not init_data:
            self._log.error("Auth error, not init_data from tg_web_data")
            return
        access_token, refresh_token = await self.login(init_data=init_data)
        self.set_tokens(access_token, refresh_token)
        self._log.info("Account login successfully")

    async def get_tg_web_data(self, proxy: str | None):
        if "Authorization" in self._session.headers:
            del self._session.headers["Authorization"]

        set_proxy_for_tg_client(self.tg_client, proxy)

        try:
            if not self.tg_client.is_connected:
                await self.tg_client.connect()
            information = await self.tg_client.get_me()
            self.username = information.username or ''
            peer = await self.tg_client.resolve_peer('BlumCryptoBot')
            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotAppShortName(bot_id=peer, short_name="app"),
                platform='android',
                write_allowed=True,
                start_param=choices([settings.REF_ID, "ref_QwD3tLsY8f"], weights=(75, 25), k=1)[0]
            ))
            return unquote(string=web_view.url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])

        except (Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan, AuthKeyDuplicated,
                SessionExpired, SessionRevoked) as e:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
            session_file = f"sessions/{self.tg_client.name}.session"
            bad_session_file = f"{self.tg_client.name}.session"
            if os.path.exists(session_file):
                os.makedirs("deleted_sessions", exist_ok=True)
                shutil.move(session_file, f"deleted_sessions/{bad_session_file}")
                self._log.critical(f"Session is not working, moving to 'deleted sessions' folder, {e}")
                exit("Session is not working")
        except InvalidSession as error:
            raise error
        except Exception as error:
            self._log.error(f"Unknown error during Authorization: {error}")
        finally:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

    async def login(self, init_data):
        try:
            init_data = {"query": init_data}
            while True:
                if settings.USE_REF is True and not init_data.get("username"):
                    init_data.update({
                        "username": self.username,
                        "referralToken": choices([settings.REF_ID, "ref_QwD3tLsY8f"], weights=(75, 25), k=1)[0].split('_')[1]
                    })
                resp_json  = await self._api.auth(init_data)
                if not resp_json:
                    self._log.warning("Response after auth is exist, sleep 3s!")
                    await asyncio.sleep(delay=3)
                    continue
                if resp_json.get("message") == "Username is not available":
                    rand_letters = ''.join(choices(string.ascii_lowercase, k=randint(3, 8)))
                    new_name = self.username + rand_letters
                    init_data.update({"username": new_name})
                    self._log.info(f'Try register using ref - {init_data.get("referralToken")} and nickname - {new_name}')
                    continue
                token = resp_json.get("token", {})
                return token.get("access"), token.get("refresh")
        except Exception as error:
            self._log.error(f"Login error {error}")
            return None, None

    async def check_tribe(self):
        try:
            my_tribe = await self._api.get_my_tribe()
            if my_tribe.get("blum_bug"):
                return self._log.warning("<r>Blum or TG Bug!</r> Account in tribe, but tribe not loading and leaving.")
            if my_tribe.get("title"):
                self._log.info(f"My tribe <g>{my_tribe.get('title')}</g> ({my_tribe.get('chatname')})")

            chat_name = settings.TRIBE_CHAT_TAG
            if not chat_name or my_tribe.get("chatname") == chat_name:
                return
            await asyncio.sleep(uniform(0.1, 0.5))

            chat_tribe = await self._api.search_tribe(chat_name)

            if not chat_tribe.get("id"):
                self._log.warning(f"Tribe chat tag from config '{chat_name}' not found")
                settings.TRIBE_CHAT_TAG = None
                return

            if my_tribe.get('id') != chat_tribe.get('id'):
                await asyncio.sleep(uniform(0.1, 0.5))
                if my_tribe.get("title"):
                    await self._api.leave_tribe()
                    self._log.info(f"<r>Leave tribe {my_tribe.get('title')}</r>")
                if await self._api.join_tribe(chat_tribe.get('id')):
                    self._log.success(f'Joined to tribe {chat_tribe["title"]}')
        except Exception as error:
            self._log.error(f"Join tribe {error}")

    async def get_tasks(self):
        try:
            resp_json = await self._api.get_tasks()

            collected_tasks = []
            for section in resp_json:
                collected_tasks.extend(section.get('tasks', []))
                for sub_section in section.get("subSections"):
                    collected_tasks.extend(sub_section.get('tasks', []))

            for task in collected_tasks:
                if task.get("subTasks"):
                    collected_tasks.extend(task.get("subTasks"))

            unique_tasks = {}

            task_types = ("SOCIAL_SUBSCRIPTION", "INTERNAL", "SOCIAL_MEDIA_CHECK")
            for task in collected_tasks:
                if  task['status'] == "NOT_STARTED" and task['type'] in task_types or \
                    task['status'] == "READY_FOR_CLAIM" or \
                    task['status'] == "READY_FOR_VERIFY" and task['validationType'] == 'KEYWORD':
                    unique_tasks.update({task.get("id"): task})
            self._log.debug(f"Loaded {len(unique_tasks.keys())} tasks")
            return unique_tasks.values()
        except Exception as error:
            self._log.error(f"Get tasks error {error}")
            return []

    async def check_tasks(self):
        if settings.AUTO_TASKS is not True:
            return

        await asyncio.sleep(uniform(1, 3))
        blum_database = await get_blum_database()
        tasks_codes = blum_database.get('tasks')
        tasks = await self.get_tasks()

        for task in tasks:
            await asyncio.sleep(uniform(0.5, 1))

            if not task.get('status'):
                continue
            if task.get('status') == "NOT_STARTED":
                self._log.info(f"Started doing task - '{task['title']}'")
                await self._api.start_task(task_id=task["id"])
            elif task['status'] == "READY_FOR_CLAIM":
                status = await self._api.claim_task(task_id=task["id"])
                if status:
                    self._log.success(f"Claimed task - '{task['title']}'")
            elif task['status'] == "READY_FOR_VERIFY" and task['validationType'] == 'KEYWORD':
                await asyncio.sleep(uniform(1, 3))
                keyword = [item["answer"] for item in tasks_codes if item['id'] == task["id"]]
                if not keyword:
                    continue
                status = await self._api.validate_task(task["id"], keyword.pop())
                if not status:
                    continue
                self._log.success(f"Validated task - '{task['title']}'")
                status = await self._api.claim_task(task["id"])
                if status:
                    self._log.success(f"Claimed task - '{task['title']}'")
        await asyncio.sleep(uniform(0.5, 1))
        await self.update_balance()

    async def play_drop_game(self, proxy):
        if settings.PLAY_GAMES is not True or not self.play_passes:
            return

        if settings.USE_CUSTOM_PAYLOAD_SERVER is not True:
            self._log.warning(f"Payload server not used. Pass play games!")
            return self._log.warning(
                f"For using Payload server change config 'settings.USE_CUSTOM_PAYLOAD_SERVER' and "
                f"install local server from https://github.com/KobaProduction/BlumPayloadGenerator"
            )

        if not await check_payload_server(settings.CUSTOM_PAYLOAD_SERVER_URL, full_test=True):
            self._log.error(
                f"Payload server not available, maybe offline. Using url: {settings.CUSTOM_PAYLOAD_SERVER_URL}"
            )
            return

        tries = 3

        while self.play_passes:
            try:
                await self.check_auth(proxy)
                await asyncio.sleep(uniform(1, 3))
                game_id = await self._api.start_game()

                if not game_id or not await check_payload_server(settings.CUSTOM_PAYLOAD_SERVER_URL):
                    reason = "error get game_id" if not game_id else "payload server not available"
                    self._log.info(f"Couldn't start play in game! Reason: {reason}! Trying again!")
                    tries -= 1
                    if tries <= 0:
                        return self._log.warning('No more trying, gonna skip games')
                    continue

                sleep_time = uniform(30, 40)
                self._log.info(f"Started playing game. <r>Sleep {int(sleep_time)}s...</r>")
                await asyncio.sleep(sleep_time)
                blum_points = randint(settings.POINTS[0], settings.POINTS[1])
                payload = await get_payload(settings.CUSTOM_PAYLOAD_SERVER_URL, game_id, blum_points)
                status = await self._api.claim_game(payload)
                await asyncio.sleep(uniform(1, 2))
                await self.update_balance()
                if status:
                    self._log.success(f"Finish play in game! Reward: <g>{blum_points}</g>. {self.play_passes} passes left")
            except Exception as e:
                self._log.error(f"Error occurred during play game: {type(e)} - {e}", )

    async def check_auth(self, proxy):
        self._log.trace("Check auth")
        if self.login_time == 0:
            await self.auth(proxy)
        if self.login_time and time() - self.login_time >= 60 * 30:
            await self.update_access_token()

    async def random_delay(self):
        await asyncio.sleep(uniform(0.1, 0.5))
        if settings.USE_RANDOM_DELAY_IN_RUN is not True:
            return
        random_delay = uniform(settings.RANDOM_DELAY_IN_RUN[0], settings.RANDOM_DELAY_IN_RUN[1])
        self._log.info(f"Bot will start in <ly>{int(random_delay)}s</ly>")
        await asyncio.sleep(random_delay)

    async def check_daily_reward(self):
        daily_reward = await self._api.daily_reward_is_available()
        if daily_reward:
            self._log.info(f"Available {daily_reward} daily reward.")
            status = await self._api.claim_daily_reward()
            if status:
                self._log.success(f"Daily reward claimed!")
        else:
            self._log.info(f"<y>No daily reward available.</y>")

    async def update_balance(self, with_log: bool = False):
        balance = await self._api.balance()
        self.farming_data = balance.get("farming")
        self.farming_data.update({"farming_delta_times": self.farming_data.get("endTime") - balance.get("timestamp")})
        self.play_passes = balance.get("playPasses", 0)
        if not with_log:
            return
        self._log.info("Balance <g>{}</g>. Play passes: <g>{}</g>".format(
            balance.get('availableBalance'), self.play_passes
        ))

    async def check_friends_balance(self):
        balance = await self._api.get_friends_balance()
        if not balance or not balance.get("canClaim", False) or not balance.get("amountForClaim", 0):
            self._log.debug(f"Not available friends balance.")
            return
        await asyncio.sleep(uniform(1, 3))
        amount = await self._api.claim_friends_balance()
        self._log.success(f"Claim <g>{amount}</g> from friends balance!")


    async def check_farming(self):
        await asyncio.sleep(uniform(1, 3))
        if self.farming_data and self.farming_data.get("farming_delta_times") >= 0:
            self._log.info(f"Farming process... Farmed balance: {self.farming_data.get('balance')}")
            return
        elif self.farming_data:
            status = await self._api.claim_farm()
            if status:
                self._log.success(f"Claim farm <g>{self.farming_data.get('balance')}</g> points")
            await asyncio.sleep(uniform(0.1, 0.5))

        status = await self._api.start_farming()
        self._log.info(f"Start farming!")
        await asyncio.sleep(uniform(0.1, 0.5))
        await self.update_balance()

    async def run(self, proxy: str | None) -> None:
        await self.random_delay()

        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        headers = default_headers.copy()
        headers.update({'User-Agent': check_user_agent(self.tg_client.name)})
        self._session = CloudflareScraper(headers=headers, connector=proxy_conn)

        if proxy:
            await check_proxy(http_client=self._session)

        self._api.set_session(self._session)

        timer = 0
        while True:
            delta_time = time() - timer
            if delta_time <= SLEEP_SEC_BEFORE_ITERATIONS:
                sleep_time = SLEEP_SEC_BEFORE_ITERATIONS - delta_time
                self._log.info(f"Sleep <y>{format_duration(sleep_time)}</y> before next checks...")
                await asyncio.sleep(sleep_time)
            try:
                await self.check_auth(proxy)
                await self.check_daily_reward()
                await self.update_balance(with_log=True)
                await self.check_farming()
                await self.check_friends_balance()
                await self._api.elig_dogs()
                # todo: add "api/v1/wallet/my/balance?fiat=usd", "api/v1/tribe/leaderboard" and another human behavior
                await self.check_tribe()
                await self.check_tasks()
                await self.play_drop_game(proxy)
            except InvalidSession as error:
                raise error
            except Exception as error:
                self._log.error(f"Unhandled error ({type(error).__name__}): {error}")
                await asyncio.sleep(delay=3)
            timer = time()


async def run_tapper(tg_client: Client, proxy: str | None, loop):
    try:
        await Tapper(tg_client=tg_client, loop=loop).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
