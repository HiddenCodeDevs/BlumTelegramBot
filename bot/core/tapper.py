import asyncio
import os
from random import randint, choices, uniform
import shutil
import string
from urllib.parse import unquote

import aiohttp
import json

from time import time

from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import (Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan,
                             AuthKeyDuplicated, SessionExpired, SessionRevoked)
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw import types

from bot.config import settings

from bot.exceptions import InvalidSession
from bot.core.agents import generate_random_user_agent, get_user_agents
from bot.core.api import BlumApi
from bot.core.headers import headers
from bot.core.helper import get_blum_database
from bot.utils.payload import check_payload_server, get_payload
from bot.utils.logger import logger, SessionLogger
from bot.utils.checkers import check_proxy



class Tapper:

    _log: SessionLogger = None
    _session: CloudflareScraper = None

    user_url = "https://user-domain.blum.codes"
    gateway_url = "https://gateway.blum.codes"
    wallet_url = "https://wallet-domain.blum.codes"
    subscription_url = "https://subscription.blum.codes"


    play_passes: int
    farming_data: dict | None

    def __init__(self, tg_client: Client):
        self.tg_client = tg_client

        self._log = SessionLogger(self.tg_client.name)
        self._api = BlumApi(self._log)

        self.user_id = 0
        self.username = None
        self.first_name = None
        self.last_name = None
        self.fullname = None
        self.start_param = None
        self.peer = None

        self.session_ug_dict = get_user_agents() or []

        headers['User-Agent'] = self.check_user_agent()

        self.refresh_token = ""
        self.login_time = 0

    async def get_new_auth_tokens(self):
        if "Authorization" in self._session.headers:
            del self._session.headers["Authorization"]
        json_data = {'refresh': self.refresh_token}
        resp = await self._session.post(f"{self.user_url}/api/v1/auth/refresh", json=json_data, ssl=False)
        resp_json = await resp.json()
        return resp_json.get('access'), resp_json.get('refresh')


    def set_tokens(self, access_token, refresh_token):
        if access_token and refresh_token:
            self._session.headers["Authorization"] = f"Bearer {access_token}"
            self.refresh_token = refresh_token
            self.login_time = time()
        else:
            self._log.error('Can`t get new token, trying again')

    async def update_access_token(self):
        access_token, refresh_token = await self.get_new_auth_tokens()
        self.set_tokens(access_token, refresh_token)
        self.login_time = time()

    async def auth(self, proxy):
        init_data = await self.get_tg_web_data(proxy=proxy)
        if not init_data:
            self._log.error("Auth error, not init_data from tg_web_data")
            return
        access_token, refresh_token = await self.login(http_client=self._session, init_data=init_data)
        self.set_tokens(access_token, refresh_token)
        self._log.info("Account login successfully")


    def save_user_agent(self):
        user_agents_file_name = "user_agents.json"

        if not any(session['session_name'] == self.tg_client.name for session in self.session_ug_dict):
            user_agent_str = generate_random_user_agent()

            self.session_ug_dict.append({
                'session_name': self.tg_client.name,
                'user_agent': user_agent_str})

            with open(user_agents_file_name, 'w') as user_agents:
                json.dump(self.session_ug_dict, user_agents, indent=4)

            self._log.success(f"User agent saved successfully")

            return user_agent_str



    def check_user_agent(self):
        load = next(
            (
                session['user_agent']
                for session in self.session_ug_dict
                if session['session_name'] == self.tg_client.name
            ), None
        )

        if load is None:
            return self.save_user_agent()

        return load

    async def get_tg_web_data(self, proxy: str | None):
        if "Authorization" in self._session.headers:
            del self._session.headers["Authorization"]
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

        self.tg_client.proxy = proxy_dict

        try:
            with_tg = True

            if not self.tg_client.is_connected:
                with_tg = False
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan, AuthKeyDuplicated,
                        SessionExpired, SessionRevoked):
                    if self.tg_client.is_connected:
                        await self.tg_client.disconnect()
                    session_file = f"sessions/{self.tg_client.name}.session"
                    bad_session_file = f"{self.tg_client.name}.session"
                    if os.path.exists(session_file):
                        os.makedirs("deleted_sessions", exist_ok=True)
                        shutil.move(session_file, f"deleted_sessions/{bad_session_file}")
                        self._log.critical(f"Session is deleted, moving to deleted sessions folder")
                    return None

            self.start_param = choices([settings.REF_ID, "ref_QwD3tLsY8f"], weights=[75, 25], k=1)[0]
            peer = await self.tg_client.resolve_peer('BlumCryptoBot')
            InputBotApp = types.InputBotAppShortName(bot_id=peer, short_name="app")

            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotApp,
                platform='android',
                write_allowed=True,
                start_param=self.start_param
            ))

            auth_url = web_view.url
            #print(auth_url)
            tg_web_data = unquote(
                string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])

            try:
                if self.user_id == 0:
                    information = await self.tg_client.get_me()
                    self.user_id = information.id
                    self.first_name = information.first_name or ''
                    self.last_name = information.last_name or ''
                    self.username = information.username or ''
            except Exception as e:
                print(e)

            if with_tg is False:
                await self.tg_client.disconnect()

            return tg_web_data

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
                await asyncio.sleep(99999999)

        except InvalidSession as error:
            raise error

        except Exception as error:
            self._log.error(f"Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)

    async def login(self, http_client: aiohttp.ClientSession, init_data):
        try:
            await http_client.options(url=f'{self.user_url}/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP')
            while True:
                if settings.USE_REF is False:
                    resp = await http_client.post(
                        url=f"{self.user_url}/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP",
                        json={"query": init_data}, ssl=False
                    )
                    if resp.status == 520:
                        self._log.warning('Relogin')
                        await asyncio.sleep(delay=3)
                        continue
                    resp_json = await resp.json()

                    return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                else:

                    json_data = {"query": init_data, "username": self.username, "referralToken": self.start_param.split('_')[1]}

                    resp = await http_client.post(f"{self.user_url}/api/v1/auth/provider"
                                                  "/PROVIDER_TELEGRAM_MINI_APP",
                                                  json=json_data, ssl=False)
                    if resp.status == 520:
                        self._log.warning('Relogin')
                        await asyncio.sleep(delay=3)
                        continue
                    #self.debug(f'login text {await resp.text()}')
                    resp_json = await resp.json()

                    if resp_json.get("message") == "Username is not available":
                        while True:
                            name = self.username
                            rand_letters = ''.join(choices(string.ascii_lowercase, k=randint(3, 8)))
                            new_name = name + rand_letters

                            json_data = {"query": init_data, "username": new_name,
                                         "referralToken": self.start_param.split('_')[1]}

                            resp = await http_client.post(
                                f"{self.user_url}/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP",
                                json=json_data, ssl=False)
                            if resp.status == 520:
                                self._log.warning('Relogin')
                                await asyncio.sleep(delay=3)
                                continue
                            #self.debug(f'login text {await resp.text()}')
                            resp_json = await resp.json()

                            if resp_json.get("token"):
                                self._log.success(f'Registered using ref - {self.start_param} and nickname - {new_name}')
                                return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                            elif resp_json.get("message") == 'account is already connected to another user':

                                resp = await http_client.post(f"{self.user_url}/api/v1/auth/provider"
                                                              "/PROVIDER_TELEGRAM_MINI_APP",
                                                              json={"query": init_data}, ssl=False)
                                if resp.status == 520:
                                    self._log.warning('Relogin')
                                    await asyncio.sleep(delay=3)
                                    continue
                                resp_json = await resp.json()
                                #self.debug(f'login text {await resp.text()}')
                                return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                            else:
                                self._log.info(f'Username taken, retrying register with new name')
                                await asyncio.sleep(1)

                    elif resp_json.get("message") == 'account is already connected to another user':

                        json_data = {"query": init_data}
                        resp = await http_client.post(f"{self.user_url}/api/v1/auth/provider"
                                                      "/PROVIDER_TELEGRAM_MINI_APP",
                                                      json=json_data, ssl=False)
                        if resp.status == 520:
                            self._log.warning('Relogin')
                            await asyncio.sleep(delay=3)
                            continue
                        resp_json = await resp.json()

                        return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                    elif resp_json.get("token"):

                        self._log.success(f'Registered using ref - {self.start_param} and nickname - {self.username}')
                        return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

        except Exception as error:
            self._log.error(f"Login error {error}")
            return None, None

    async def check_tribe(self):
        try:

            my_tribe = await self._api.get_my_tribe()
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
            self._log.error(f"=Join tribe {error}")


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
            for task in collected_tasks:
                if task.get("status") == "FINISHED":
                    continue
                if task.get("progressTarget") and \
                    task.get("progressTarget", {}).get('target') > \
                    task.get("progressTarget", {}).get('progress'):
                    continue
                # print(task.get("status"), task, "\n")
                unique_tasks.update({task.get("id"): task})
            self._log.debug(f"Loaded {len(unique_tasks.keys())} tasks")
            return unique_tasks.values()
        except Exception as error:
            self._log.error(f"Get tasks error {error}")
            return []

    async def check_tasks(self):
        if not settings.AUTO_TASKS:
            return

        await asyncio.sleep(uniform(1, 3))
        blum_database = await get_blum_database()
        tasks_codes = blum_database.get('tasks')
        tasks = await self.get_tasks()

        for task in tasks:
            await asyncio.sleep(uniform(0.5, 1))

            if not task.get('status'):
                continue

            if task.get('status') == "NOT_STARTED" and task.get('type') == "PROGRESS_TARGET":
                self._log.info(f"Started doing task - '{task['title']}'")
                await self._api.start_task(task_id=task["id"])
            elif task['status'] == "READY_FOR_CLAIM" and task['type'] != 'PROGRESS_TASK':
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
        if settings.PLAY_GAMES is False and not self.play_passes:
            return

        if not settings.USE_CUSTOM_PAYLOAD_SERVER:
            self._log.warning(f"Payload server not used. Pass play games!")
            return

        if not await check_payload_server(settings.CUSTOM_PAYLOAD_SERVER_URL, full_test=True):
            self._log.error(f"Payload server not available, maybe offline. Url: {settings.CUSTOM_PAYLOAD_SERVER_URL}")
            return

        tries = 3

        while self.play_passes:
            try:
                # self._log.debug("sleep before start")
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
                self._log.info(f"Started playing game ({game_id}). <r>Sleep {int(sleep_time)}s...</r>")
                await asyncio.sleep(sleep_time)

                blum_points = randint(settings.POINTS[0], settings.POINTS[1])
                # dogs = random.randint(25, 30) * 5 if await self._api.elig_dogs() else 0

                # data = await self.create_payload(http_client=http_client, game_id=game_id, points=points, dogs=dogs)

                payload = await get_payload(settings.CUSTOM_PAYLOAD_SERVER_URL, game_id, blum_points)
                status = await self._api.claim_game(payload)
                await asyncio.sleep(uniform(1, 2))
                await self.update_balance()
                if status:
                    self._log.success(f"Finish play in game! Reward: <g>{blum_points}</g>. {self.play_passes} passes left")
            except Exception as e:
                self._log.error(f"Error occurred during play game: {e}")

    async def check_auth(self, proxy):
        if self.login_time == 0:
            await self.auth(proxy)
        if self.login_time and time() - self.login_time >= 60 * 30:
            await self.update_access_token()

    async def random_delay(self):
        random_delay = randint(settings.RANDOM_DELAY_IN_RUN[0], settings.RANDOM_DELAY_IN_RUN[1])
        self._log.info(f"Bot will start in <ly>{random_delay}s</ly>")
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
        self.play_passes = balance.get("playPasses", 0)
        if not with_log:
            return
        self._log.info("Balance <g>{}</g>. Play passes: <g>{}</g>".format(
            balance.get('availableBalance'), self.play_passes
        ))

    async def check_friends_balance(self):
        balance = await self._api.get_friends_balance()
        if not balance or not balance.get("canClaim", False) or not balance.get("amountForClaim", 0):
            return
        await asyncio.sleep(uniform(1, 3))
        amount = await self._api.claim_friends_balance()
        self._log.success(f"Claim <g>{amount}</g> from friends balance!")


    async def check_farming(self):
        await asyncio.sleep(uniform(1, 3))
        if not self.farming_data:
            status = await self._api.start_farming()
            self._log.info(f"Start farming: {status}")
            return

        if self.farming_data.get("endTime") and self.farming_data.get("endTime") - time() >= 0:
            self._log.info(f"Farming process... Farm balance: {self.farming_data.get('balance')}")
            return
        amount = await self._api.claim_farm()
        self._log.success(f"Claim farm <g>{amount}</g> points")

    async def run(self, proxy: str | None) -> None:
        if settings.USE_RANDOM_DELAY_IN_RUN:
            await self.random_delay()

        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None
        self._session = CloudflareScraper(headers=headers, connector=proxy_conn)

        if proxy:
            await check_proxy(http_client=self._session)

        self._api.set_session(self._session)

        timer = 0
        while True:
            try:
                delta_time = time() - timer
                if delta_time <= 60 * 5:
                    await asyncio.sleep(60 * 5 - delta_time)

                await self.check_auth(proxy)
                await self.check_daily_reward()
                await self.update_balance(with_log=True)
                await self.check_farming()
                await self.check_friends_balance()
                await self.check_tribe()
                await self.check_tasks()
                await self.play_drop_game(proxy)

                timer = time()
            except InvalidSession as error:
                raise error
            except Exception as error:
                self._log.error(f"Unknown error: {error}")
                await asyncio.sleep(delay=3)


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
