import asyncio
import os
import random
import shutil
import string
from urllib.parse import unquote

import aiohttp
import json

from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import (Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan,
                             AuthKeyDuplicated, SessionExpired, SessionRevoked)
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw import types

from bot.core.agents import generate_random_user_agent, get_user_agents
from bot.config import settings

from bot.exceptions import InvalidSession
from bot.core.api import BlumApi
from bot.core.headers import headers
from bot.core.helper import format_duration
from bot.utils.payload import check_payload_server, get_payload
from bot.utils.logger import logger, SessionLogger
from bot.utils.checkers import check_proxy



class Tapper:

    _log: SessionLogger = None

    user_url = "https://user-domain.blum.codes"
    gateway_url = "https://gateway.blum.codes"
    wallet_url = "https://wallet-domain.blum.codes"
    subscription_url = "https://subscription.blum.codes"
    tribe_url = "https://tribe-domain.blum.codes"

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
        self.first_run = None

        self.session_ug_dict = get_user_agents() or []

        headers['User-Agent'] = self.check_user_agent()

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
            (session['user_agent'] for session in self.session_ug_dict if session['session_name'] == self.tg_client.name),
            None)

        if load is None:
            return self.save_user_agent()

        return load

    async def get_tg_web_data(self, proxy: str | None):
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

            self.start_param = random.choices([settings.REF_ID, "ref_QwD3tLsY8f"], weights=[75, 25], k=1)[0]
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
                            rand_letters = ''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 8)))
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





    async def validate_task(self, http_client: aiohttp.ClientSession, task_id):
        try:
            url = 'https://raw.githubusercontent.com/zuydd/database/main/blum.json'
            request = await http_client.get(url=url)
            blum_database = await request.json()

            tasks = blum_database.get('tasks')

            keyword = [item["answer"] for item in tasks if item['id'] == task_id]


            status = await self._api.validate_task(task_id, keyword.pop())
            if status:
                status = await self._api.claim_task(task_id)
                if status:
                    return status
            else:
                return False

        except Exception as error:
            self._log.error(f"Claim task error {error}")

    async def join_tribe(self, http_client: aiohttp.ClientSession):
        try:
            chat_name = settings.TRIBE_CHAT_TAG
            info_resp = await http_client.get(f'{self.tribe_url}/api/v1/tribe/by-chatname/{chat_name}', ssl=False)
            info = await info_resp.json()

            tribe_id = info.get('id')
            tribe_name = info.get('title')

            my_tribe_inf = await http_client.get('https://tribe-domain.blum.codes/api/v1/tribe/my', ssl=False)
            my_tribe = await my_tribe_inf.json()
            my_tribe_id = my_tribe.get('id', None)

            if my_tribe_id != tribe_id or not my_tribe_id:
                await http_client.post(f'{self.tribe_url}/api/v1/tribe/leave', json={}, ssl=False)

                resp = await http_client.post(f'{self.tribe_url}/api/v1/tribe/{tribe_id}/join', ssl=False)
                text = await resp.text()
                if text == 'OK':
                    self._log.success(f'Joined to tribe {tribe_name}')
        except Exception as error:
            self._log.error(f"=Join tribe {error}")


    async def get_tasks(self):
        try:
            resp_json = await self._api.get_tasks()

            collected_tasks = []
            for task in resp_json:
                if task.get('sectionType') == 'HIGHLIGHTS':
                    tasks_list = task.get('tasks', [])
                    for t in tasks_list:
                        sub_tasks = t.get('subTasks')
                        if sub_tasks:
                            for sub_task in sub_tasks:
                                collected_tasks.append(sub_task)
                        if t.get('type') != 'PARTNER_INTEGRATION':
                            collected_tasks.append(t)
                        if t.get('type') == 'PARTNER_INTEGRATION' and t.get('reward'):
                            collected_tasks.append(t)

                if task.get('sectionType') == 'WEEKLY_ROUTINE':
                    tasks_list = task.get('tasks', [])
                    for t in tasks_list:
                        sub_tasks = t.get('subTasks', [])
                        for sub_task in sub_tasks:
                            # print(sub_task)
                            collected_tasks.append(sub_task)

                if task.get('sectionType') == "DEFAULT":
                    sub_tasks = task.get('subSections', [])
                    for sub_task in sub_tasks:
                        tasks = sub_task.get('tasks', [])
                        for task_basic in tasks:
                            collected_tasks.append(task_basic)

            return collected_tasks
        except Exception as error:
            self._log.error(f"Get tasks error {error}")
            return []

    async def update_auth(self, http_client, refresh_token):
        access_token, refresh_token = await self.refresh_token(http_client=http_client, token=refresh_token)
        if access_token:
            http_client.headers["Authorization"] = f"Bearer {access_token}"

    async def play_game(self, play_passes):

        if settings.USE_CUSTOM_PAYLOAD_SERVER:
            self._log.warning(f"Payload server not used. Pass play games!")

        if not await check_payload_server(settings.CUSTOM_PAYLOAD_SERVER_URL):
            self._log.error(f"Payload server not available, maybe offline. Url: {settings.CUSTOM_PAYLOAD_SERVER_URL}")
            return

        number_of_games = 25 if play_passes > 25 else play_passes
        tries = 3

        for _ in range(number_of_games):
            try:
                await asyncio.sleep(random.uniform(1, 5))
                game_id = await self._api.start_game()
                if not game_id:
                    self._log.info(f"Couldn't start play in game! play_passes: {play_passes}, trying again")
                if not game_id:
                    tries -= 1
                    if tries <= 0:
                        return self._log.warning('No more trying, gonna skip games')
                    continue


                sleep_time = random.uniform(30, 40)
                self._log.success(f"Started playing game ({game_id}). Sleep: {sleep_time}")
                await asyncio.sleep(sleep_time)

                blum_points = random.randint(settings.POINTS[0], settings.POINTS[1])
                # dogs = random.randint(25, 30) * 5 if await self._api.elig_dogs() else 0

                # data = await self.create_payload(http_client=http_client, game_id=game_id, points=points, dogs=dogs)

                payload = await get_payload(settings.CUSTOM_PAYLOAD_SERVER_URL, game_id, blum_points)
                status = await self._api.claim_game(payload.get("payload"))
                if status:
                    play_passes -= 1
                    self._log.info(f"Finish play in game! Reward: {blum_points}")
            except Exception as e:
                self._log.error(f"Error occurred during play game: {e}")











    async def refresh_token(self, http_client: aiohttp.ClientSession, token):
        if "Authorization" in http_client.headers:
            del http_client.headers["Authorization"]
        json_data = {'refresh': token}
        resp = await http_client.post(f"{self.user_url}/api/v1/auth/refresh", json=json_data, ssl=False)
        resp_json = await resp.json()

        return resp_json.get('access'), resp_json.get('refresh')


    async def run(self, proxy: str | None) -> None:
        if settings.USE_RANDOM_DELAY_IN_RUN:
            random_delay = random.randint(settings.RANDOM_DELAY_IN_RUN[0], settings.RANDOM_DELAY_IN_RUN[1])
            self._log.info(f"Bot will start in <ly>{random_delay}s</ly>")
            await asyncio.sleep(random_delay)

        refresh_token = None
        login_need = True

        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)

        self._api.set_session(http_client)

        if proxy:
            await check_proxy(http_client=http_client)

        while True:
            try:
                if login_need:
                    if "Authorization" in http_client.headers:
                        del http_client.headers["Authorization"]

                    init_data = await self.get_tg_web_data(proxy=proxy)
                    if init_data:
                        access_token, refresh_token = await self.login(http_client=http_client, init_data=init_data)
                        if access_token and refresh_token:
                            http_client.headers["Authorization"] = f"Bearer {access_token}"

                        if self.first_run is not True:
                            self._log.success("Logged in successfully")
                            self.first_run = True

                timestamp, start_time, end_time, play_passes = await self._api.balance()

                if isinstance(play_passes, int) and login_need:
                    self._log.info(f'You have {play_passes} play passes')
                    login_need = False

                msg = await self._api.claim_daily_reward()
                if isinstance(msg, bool) and msg:
                    self._log.success(f"Claimed daily reward!")

                claim_amount, is_available = await self._api.friend_balance()

                if claim_amount != 0 and is_available:
                    amount = await self._api.friend_claim()
                    self._log.success(f"Claimed friend ref reward {amount}")

                if settings.PLAY_GAMES is True and play_passes and play_passes > 0:
                    await self.play_game(play_passes=play_passes)

                await self.join_tribe(http_client=http_client)

                if settings.AUTO_TASKS:
                    tasks = await self.get_tasks()

                    for task in tasks:
                        if task.get('status') == "NOT_STARTED" and task.get('type') != "PROGRESS_TARGET":
                            self._log.info(f"Started doing task - '{task['title']}'")
                            await self._api.start_task(task_id=task["id"])
                            await asyncio.sleep(0.5)

                    await asyncio.sleep(5)

                    tasks = await self.get_tasks()
                    for task in tasks:
                        if task.get('status'):
                            if task['status'] == "READY_FOR_CLAIM" and task['type'] != 'PROGRESS_TASK':
                                status = await self._api.claim_task(task_id=task["id"])
                                if status:
                                    self._log.success(f"Claimed task - '{task['title']}'")
                                await asyncio.sleep(0.5)
                            elif task['status'] == "READY_FOR_VERIFY" and task['validationType'] == 'KEYWORD':
                                status = await self.validate_task(http_client, task_id=task["id"])
                                if status:
                                    self._log.success(f"Validated task - '{task['title']}'")

                #await asyncio.sleep(random.uniform(1, 3))

                try:
                    timestamp, start_time, end_time, play_passes = await self._api.balance()

                    if start_time is None and end_time is None:
                        await self._api.start_farming()
                        self._log.info(f"<lc>[FARMING]</lc> Start farming!")

                    elif (start_time is not None and end_time is not None and timestamp is not None and
                          timestamp >= end_time):
                        timestamp, balance = await self._api.claim_farm()
                        self._log.success(f"<lc>[FARMING]</lc> Claimed reward! Balance: {balance}")

                    elif end_time is not None and timestamp is not None:
                        sleep_duration = end_time - timestamp
                        self._log.info(f"<lc>[FARMING]</lc> Sleep {format_duration(sleep_duration)}")
                        login_need = True
                        await asyncio.sleep(sleep_duration)

                except Exception as e:
                    self._log.error(f"<lc>[FARMING]</lc> Error in farming management: {e}")

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
