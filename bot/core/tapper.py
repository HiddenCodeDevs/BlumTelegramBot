import asyncio
import traceback
from random import randint, uniform
from time import time

from better_proxy import Proxy
from aiocfscrape import CloudflareScraper
from aiohttp_socks import ProxyConnector
from pyrogram import Client

from bot.config import settings
from bot.core.agents import check_user_agent
from bot.core.api import BlumApi
from bot.core.headers import headers as default_headers
from bot.core.helper import get_blum_database, set_proxy_for_tg_client, format_duration, move_session_to_deleted
from bot.core.tg_auth import get_tg_web_data
from bot.exceptions import NeedReLoginError, TelegramInvalidSessionException, TelegramProxyError
from bot.utils.payload import check_payload_server, get_payload
from bot.utils.logger import SessionLogger
from bot.utils.checkers import check_proxy, wait_proxy


class Tapper:

    play_passes: int
    farming_data: dict | None
    _log: SessionLogger
    _session: CloudflareScraper
    _api: BlumApi
    _balance: float

    def __init__(self, tg_client: Client, log: SessionLogger):
        self.tg_client = tg_client
        self._log = log

    async def auth(self, session: CloudflareScraper):
        self._api = BlumApi(session, self._log)
        web_data_params = await get_tg_web_data(self.tg_client, self._log)
        self._log.trace("Got init data for auth.")
        if not web_data_params:
            self._log.error("Auth error, not init_data from tg_web_data")
            return
        await self._api.login(web_data_params=web_data_params)
        self._log.info("Account login successfully")

    async def check_tribe(self):
        try:
            my_tribe = await self._api.get_my_tribe()
            self._log.trace(f"my_tribe got: {my_tribe}")
            if not isinstance(my_tribe, dict):
                self._log.warning(f"Unknown my tribe data: {my_tribe}")
                return
            if my_tribe.get("blum_bug"):
                return self._log.warning("<r>Blum or TG Bug!</r> Account in tribe, but tribe not loading and leaving.")
            if my_tribe.get("title"):
                self._log.info(f"My tribe <g>{my_tribe.get('title')}</g> ({my_tribe.get('chatname')})")

            chat_name = settings.TRIBE_CHAT_TAG
            if not chat_name or my_tribe.get("chatname") == chat_name:
                return
            await asyncio.sleep(uniform(0.1, 0.5))

            chat_tribe = await self._api.search_tribe(chat_name)

            if not chat_tribe or not chat_tribe.get("id"):
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
            self._log.error(f"{traceback.format_exc()}")

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

    async def check_tasks(self) -> bool:
        if settings.AUTO_TASKS is not True:
            return False

        await asyncio.sleep(uniform(1, 3))
        blum_database = await get_blum_database()
        tasks_codes = blum_database.get('tasks')
        tasks = await self.get_tasks()

        is_task_started = False

        for task in tasks:
            await asyncio.sleep(uniform(0.5, 1))

            if not task.get('status'):
                continue
            if task.get('status') == "NOT_STARTED":
                self._log.info(f"Started doing task - '{task['title']}'")
                is_task_started = await self._api.start_task(task_id=task["id"])
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
        await self.update_user_balance()
        await self.update_points_balance()
        return is_task_started

    async def play_drop_game(self):
        if settings.PLAY_GAMES is not True or not self.play_passes:
            return

        if settings.USE_CUSTOM_PAYLOAD_SERVER is not True:
            return self._log.warning(f"Payload server not used. Pass play games!")

        if not await check_payload_server(settings.CUSTOM_PAYLOAD_SERVER_URL, full_test=True):
            self._log.warning(
                f"Payload server not available. Skip games... "
                f"Info: https://github.com/HiddenCodeDevs/BlumTelegramBot/blob/main/PAYLOAD-SERVER.MD"
            )
            return

        tries = 3

        while self.play_passes:
            if tries <= 0:
                return self._log.warning('No more trying, gonna skip games')
            if not await check_payload_server(settings.CUSTOM_PAYLOAD_SERVER_URL):
                self._log.info(f"Couldn't start play in game! Reason: payload server not available")
                tries -= 1
                continue


            await asyncio.sleep(uniform(1, 3))
            game_data = await self._api.start_game()
            game_assets = game_data.get("assets", {})
            game_id = game_data.get("gameId")
            if not game_id:
                self._log.info(f"Couldn't start play in game! Reason: error get game_id!")
                tries -= 1
                continue

            is_normal_structure = True

            for asset in ("BOMB", "CLOVER", "FREEZE"):
                if not asset in game_assets:
                    is_normal_structure = False
                    break

            if not is_normal_structure:
                settings.PLAY_GAMES = False
                self._log.error("<r>STOP PLAYING GAMES!</r> Unknown game data structure. Say developers for this!")

            sleep_time = uniform(30, 42)
            self._log.info(f"Started playing game. <r>Sleep {int(sleep_time)}s...</r>")

            await asyncio.sleep(sleep_time)
            freezes = int((sleep_time - 30) / 3)
            clover = randint(settings.POINTS[0], settings.POINTS[1]) # blum points

            blum_amount = clover
            earned_points = {"BP": {"amount": blum_amount}}
            asset_clicks = {
                "BOMB": {"clicks": 0},
                "CLOVER": {"clicks": clover},
                "FREEZE": {"clicks": freezes},
            }

            payload = await get_payload(settings.CUSTOM_PAYLOAD_SERVER_URL, game_id, earned_points, asset_clicks)
            status = await self._api.claim_game(payload)
            await asyncio.sleep(uniform(1, 2))
            await self.update_user_balance()
            await self.update_points_balance()
            if status:
                self._log.success(f"Finish play in game! Reward: <g>{blum_amount}</g>. "
                                  f"Balance: <y>{self._balance}</y>, <r>{self.play_passes}</r> play passes.")

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

    async def update_points_balance(self, with_log: bool = False):
        await asyncio.sleep(uniform(0.1, 0.5))
        balance = await self._api.my_points_balance()
        if not balance:
            return
        points = balance.get("points", [])
        for point in points:
            balance = float(point.get("balance"))
            if point.get("symbol") == "BP":
                self._balance = balance
            if point.get("symbol") == "PP":
                self.play_passes = int(balance)
        if not with_log:
            return
        self._log.info("Balance <g>{}</g>. Play passes: <g>{}</g>".format(
            self._balance, self.play_passes
        ))

    async def update_user_balance(self):
        balance = await self._api.user_balance()
        if not balance:
            raise Exception("Failed to get balance.")
        self.farming_data = balance.get("farming")
        if self.farming_data:
            self.farming_data.update({"farming_delta_times": self.farming_data.get("endTime") - balance.get("timestamp")})
        self.play_passes = balance.get("playPasses", 0)
        self._balance = balance.get('availableBalance') or self._balance

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

        await self._api.start_farming()
        self._log.info(f"Start farming!")
        await asyncio.sleep(uniform(0.1, 0.5))
        await self.update_user_balance()

    async def run(self, proxy: Proxy | None) -> None:
        if not settings.DEBUG:
            await self.random_delay()

        proxy_conn = ProxyConnector().from_url(proxy.as_url) if proxy else None
        headers = default_headers.copy()
        headers.update({'User-Agent': check_user_agent(self.tg_client.name)})
        async with CloudflareScraper(headers=headers, connector=proxy_conn) as session:
            if proxy:
                ip = await check_proxy(session)
                if not ip:
                    self._log.warning(f"Proxy {proxy} not available. Waiting for the moment when it will work...")
                    ip = await wait_proxy(session)
                self._log.info(f"Used proxy <y>{proxy}</y>. Real ip: <g>{ip}</g>")
                set_proxy_for_tg_client(self.tg_client, proxy)
            else:
                self._log.warning("Proxy not installed! This may lead to account ban! Be careful.")
            try:
                await self.auth(session)
            except TelegramProxyError:
                return self._log.error(f"<r>The selected proxy cannot be applied to the Telegram client.</r>")
            except Exception as e:
                self._log.error(f"{traceback.format_exc()}")
                return self._log.critical(f"Stop Tapper. Reason: {e}")

            timer = 0
            while True:
                delta_time = time() - timer
                sleep_time = uniform(
                    settings.SLEEP_MINUTES_BEFORE_ITERATIONS[0],
                    settings.SLEEP_MINUTES_BEFORE_ITERATIONS[1]
                ) * 60
                if delta_time <= sleep_time:
                    sleep_time = sleep_time - delta_time
                    self._log.info(f"Sleep <y>{format_duration(sleep_time)}</y> before next checks...")
                    await asyncio.sleep(sleep_time)
                try:
                    await self.check_daily_reward()
                    await self.update_user_balance()
                    await self.update_points_balance(with_log=True)
                    await self.check_farming()
                    await self.check_friends_balance()
                    await self._api.elig_dogs()
                    # todo: add "api/v1/wallet/my/balance?fiat=usd", "api/v1/tribe/leaderboard" and another human behavior
                    await self.check_tribe()
                    need_recheck_tasks = await self.check_tasks()
                    await self.play_drop_game()
                    if need_recheck_tasks:
                        await self.check_tasks()
                except NeedReLoginError:
                    await self.auth(session)
                except Exception:
                    self._log.error(f"{traceback.format_exc()}")
                    self._log.error(f"<r>Unhandled error</r>")
                    await asyncio.sleep(delay=3)
                timer = time()


async def run_tapper(tg_client: Client, proxy: Proxy | None):
    session_logger = SessionLogger(tg_client.name)
    try:
        await Tapper(tg_client, session_logger).run(proxy=proxy)
    except TelegramInvalidSessionException:
        move_session_to_deleted(tg_client)
        session_logger.error(f"Telegram account {tg_client.name} is not work!")
