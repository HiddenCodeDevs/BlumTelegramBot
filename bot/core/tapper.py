import asyncio
import random
import string
from time import time
from urllib.parse import unquote, quote

import aiohttp
import json
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw import types
from .agents import generate_random_user_agent
from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from .helper import format_duration


class Tapper:
    def __init__(self, tg_client: Client):
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.user_id = 0
        self.username = None
        self.first_name = None
        self.last_name = None
        self.fullname = None
        self.start_param = None
        self.peer = None
        self.first_run = None

        self.session_ug_dict = self.load_user_agents() or []

        headers['User-Agent'] = self.check_user_agent()

    async def generate_random_user_agent(self):
        return generate_random_user_agent(device_type='android', browser_type='chrome')

    def info(self, message):
        from bot.utils import info
        info(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def debug(self, message):
        from bot.utils import debug
        debug(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def warning(self, message):
        from bot.utils import warning
        warning(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def error(self, message):
        from bot.utils import error
        error(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def critical(self, message):
        from bot.utils import critical
        critical(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def success(self, message):
        from bot.utils import success
        success(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def save_user_agent(self):
        user_agents_file_name = "user_agents.json"

        if not any(session['session_name'] == self.session_name for session in self.session_ug_dict):
            user_agent_str = generate_random_user_agent()

            self.session_ug_dict.append({
                'session_name': self.session_name,
                'user_agent': user_agent_str})

            with open(user_agents_file_name, 'w') as user_agents:
                json.dump(self.session_ug_dict, user_agents, indent=4)

            logger.success(f"<light-yellow>{self.session_name}</light-yellow> | User agent saved successfully")

            return user_agent_str

    def load_user_agents(self):
        user_agents_file_name = "user_agents.json"

        try:
            with open(user_agents_file_name, 'r') as user_agents:
                session_data = json.load(user_agents)
                if isinstance(session_data, list):
                    return session_data

        except FileNotFoundError:
            logger.warning("User agents file not found, creating...")

        except json.JSONDecodeError:
            logger.warning("User agents file is empty or corrupted.")

        return []

    def check_user_agent(self):
        load = next(
            (session['user_agent'] for session in self.session_ug_dict if session['session_name'] == self.session_name),
            None)

        if load is None:
            return self.save_user_agent()

        return load

    async def get_tg_web_data(self, proxy: str | None) -> str:
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
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            if settings.REF_ID == '':
                self.start_param = 'ref_QwD3tLsY8f'
            else:
                self.start_param = settings.REF_ID

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
            print(auth_url)
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

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)

    async def login(self, http_client: aiohttp.ClientSession, initdata):
        try:
            if settings.USE_REF is False:

                json_data = {"query": initdata}
                resp = await http_client.post("https://gateway.blum.codes/v1/auth/provider"
                                              "/PROVIDER_TELEGRAM_MINI_APP",
                                              json=json_data, ssl=False)
                self.debug(f'login text {await resp.text()}')
                resp_json = await resp.json()

                return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

            else:

                json_data = {"query": initdata, "username": self.username,
                             "referralToken": self.start_param.split('_')[1]}

                resp = await http_client.post("https://gateway.blum.codes/v1/auth/provider"
                                              "/PROVIDER_TELEGRAM_MINI_APP",
                                              json=json_data, ssl=False)
                self.debug(f'login text {await resp.text()}')
                resp_json = await resp.json()

                if resp_json.get("message") == "rpc error: code = AlreadyExists desc = Username is not available":
                    while True:
                        name = self.username
                        rand_letters = ''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 8)))
                        new_name = name + rand_letters

                        json_data = {"query": initdata, "username": new_name,
                                     "referralToken": self.start_param.split('_')[1]}

                        resp = await http_client.post(
                            "https://gateway.blum.codes/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP",
                            json=json_data, ssl=False)
                        self.debug(f'login text {await resp.text()}')
                        resp_json = await resp.json()

                        if resp_json.get("token"):
                            self.success(f'Registered using ref - {self.start_param} and nickname - {new_name}')
                            return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                        elif resp_json.get("message") == 'account is already connected to another user':

                            json_data = {"query": initdata}
                            resp = await http_client.post("https://gateway.blum.codes/v1/auth/provider"
                                                          "/PROVIDER_TELEGRAM_MINI_APP",
                                                          json=json_data, ssl=False)
                            resp_json = await resp.json()
                            self.debug(f'login text {await resp.text()}')
                            return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                        else:
                            self.info(f'Username taken, retrying register with new name')
                            await asyncio.sleep(1)

                elif resp_json.get("message") == 'account is already connected to another user':

                    json_data = {"query": initdata}
                    resp = await http_client.post("https://gateway.blum.codes/v1/auth/provider"
                                                  "/PROVIDER_TELEGRAM_MINI_APP",
                                                  json=json_data, ssl=False)
                    self.debug(f'login text {await resp.text()}')
                    resp_json = await resp.json()

                    return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                elif resp_json.get("token"):

                    self.success(f'Registered using ref - {self.start_param} and nickname - {self.username}')
                    return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")


        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Login error {error}")

    async def claim_task(self, http_client: aiohttp.ClientSession, task):
        try:
            resp = await http_client.post(f'https://game-domain.blum.codes/api/v1/tasks/{task["id"]}/claim',
                                          ssl=False)
            resp_json = await resp.json()

            logger.debug(f"{self.session_name} | claim_task response: {resp_json}")

            return resp_json.get('status') == "CLAIMED"
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Claim task error {error}")

    async def start_complete_task(self, http_client: aiohttp.ClientSession, task):
        try:
            resp = await http_client.post(f'https://game-domain.blum.codes/api/v1/tasks/{task["id"]}/start',
                                          ssl=False)
            resp_json = await resp.json()

            logger.debug(f"{self.session_name} | start_complete_task response: {resp_json}")
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Start complete error {error}")

    async def get_tasks(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.get('https://game-domain.blum.codes/api/v1/tasks', ssl=False)
            resp_json = await resp.json()

            logger.debug(f"{self.session_name} | get_tasks response: {resp_json}")

            if isinstance(resp_json, list):
                return resp_json
            else:
                logger.error(f"{self.session_name} | Unexpected response format in get_tasks: {resp_json}")
                return []
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Get tasks error {error}")

    async def play_game(self, http_client: aiohttp.ClientSession, play_passes):
        try:
            while play_passes:
                game_id = await self.start_game(http_client=http_client)

                if not game_id or game_id == "cannot start game":
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Couldn't start play in game!"
                                f" play_passes: {play_passes}")
                    break
                else:
                    self.success("Started playing game")

                await asyncio.sleep(random.uniform(30, 40))

                msg, points = await self.claim_game(game_id=game_id, http_client=http_client)
                if isinstance(msg, bool) and msg:
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Finish play in game!"
                                f" reward: {points}")
                else:
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Couldn't play game,"
                                f" msg: {msg} play_passes: {play_passes}")
                    break

                await asyncio.sleep(random.uniform(30, 40))

                play_passes -= 1
        except Exception as e:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Error occurred during play game: {e}")
            await asyncio.sleep(random.randint(0, 5))

    async def start_game(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://game-domain.blum.codes/api/v1/game/play", ssl=False)
            response_data = await resp.json()
            if "gameId" in response_data:
                return response_data.get("gameId")
            elif "message" in response_data:
                return response_data.get("message")
        except Exception as e:
            self.error(f"Error occurred during start game: {e}")

    async def claim_game(self, game_id: str, http_client: aiohttp.ClientSession):
        try:
            points = random.randint(settings.POINTS[0], settings.POINTS[1])
            json_data = {"gameId": game_id, "points": points}

            resp = await http_client.post("https://game-domain.blum.codes/api/v1/game/claim", json=json_data,
                                          ssl=False)
            if resp.status != 200:
                resp = await http_client.post("https://game-domain.blum.codes/api/v1/game/claim", json=json_data,
                                              ssl=False)

            txt = await resp.text()

            return True if txt == 'OK' else txt, points
        except Exception as e:
            self.error(f"Error occurred during claim game: {e}")

    async def claim(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://game-domain.blum.codes/api/v1/farming/claim", ssl=False)
            if resp.status != 200:
                resp = await http_client.post("https://game-domain.blum.codes/api/v1/farming/claim", ssl=False)

            resp_json = await resp.json()

            return int(resp_json.get("timestamp") / 1000), resp_json.get("availableBalance")
        except Exception as e:
            self.error(f"Error occurred during claim: {e}")

    async def start(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://game-domain.blum.codes/api/v1/farming/start", ssl=False)

            if resp.status != 200:
                resp = await http_client.post("https://game-domain.blum.codes/api/v1/farming/start", ssl=False)
        except Exception as e:
            self.error(f"Error occurred during start: {e}")

    async def friend_balance(self, http_client: aiohttp.ClientSession):
        try:

            resp = await http_client.get("https://gateway.blum.codes/v1/friends/balance", ssl=False)
            resp_json = await resp.json()

            claim_amount = resp_json.get("amountForClaim")
            is_available = resp_json.get("canClaim")

            if resp.status != 200:
                resp = await http_client.get("https://gateway.blum.codes/v1/friends/balance", ssl=False)
                resp_json = await resp.json()
                claim_amount = resp_json.get("amountForClaim")
                is_available = resp_json.get("canClaim")

            return (claim_amount,
                    is_available)
        except Exception as e:
            self.error(f"Error occurred during friend balance: {e}")

    async def friend_claim(self, http_client: aiohttp.ClientSession):
        try:


            resp = await http_client.post("https://gateway.blum.codes/v1/friends/claim", ssl=False)
            resp_json = await resp.json()
            amount = resp_json.get("claimBalance")
            if resp.status != 200:
                resp = await http_client.post("https://gateway.blum.codes/v1/friends/claim", ssl=False)
                resp_json = await resp.json()
                amount = resp_json.get("claimBalance")



            return amount
        except Exception as e:
            self.error(f"Error occurred during friends claim: {e}")

    async def balance(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.get("https://game-domain.blum.codes/api/v1/user/balance", ssl=False)
            resp_json = await resp.json()

            timestamp = resp_json.get("timestamp")
            play_passes = resp_json.get("playPasses")

            start_time = None
            end_time = None
            if resp_json.get("farming"):
                start_time = resp_json["farming"].get("startTime")
                end_time = resp_json["farming"].get("endTime")

            return (int(timestamp / 1000) if timestamp is not None else None,
                    int(start_time / 1000) if start_time is not None else None,
                    int(end_time / 1000) if end_time is not None else None,
                    play_passes)
        except Exception as e:
            self.error(f"Error occurred during balance: {e}")

    async def claim_daily_reward(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://game-domain.blum.codes/api/v1/daily-reward?offset=-180",
                                          ssl=False)
            txt = await resp.text()
            return True if txt == 'OK' else txt
        except Exception as e:
            self.error(f"Error occurred during claim daily reward: {e}")

    async def refresh_token(self, http_client: aiohttp.ClientSession, token):
        json_data = {'refresh': token}
        resp = await http_client.post("https://gateway.blum.codes/v1/auth/refresh", json=json_data, ssl=False)
        resp_json = await resp.json()
        #print(f'refresh {resp_json}')

        return resp_json.get('access'), resp_json.get('refresh')

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Proxy: {proxy} | Error: {error}")

    async def run(self, proxy: str | None) -> None:
        access_token = None
        refresh_token = None
        login_need = True

        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)

        if proxy:
            await self.check_proxy(http_client=http_client, proxy=proxy)

        #print(init_data)

        while True:
            try:
                if login_need:
                    if "Authorization" in http_client.headers:
                        del http_client.headers["Authorization"]

                    init_data = await self.get_tg_web_data(proxy=proxy)

                    access_token, refresh_token = await self.login(http_client=http_client, initdata=init_data)

                    http_client.headers["Authorization"] = f"Bearer {access_token}"

                    if self.first_run is not True:
                        self.success("Logged in successfully")
                        self.first_run = True

                    login_need = False

                msg = await self.claim_daily_reward(http_client=http_client)
                if isinstance(msg, bool) and msg:
                    logger.success(f"<light-yellow>{self.session_name}</light-yellow> | Claimed daily reward!")

                timestamp, start_time, end_time, play_passes = await self.balance(http_client=http_client)

                if isinstance(play_passes, int):
                    self.info(f'You have {play_passes} play passes')

                claim_amount, is_available = await self.friend_balance(http_client=http_client)

                if claim_amount != 0 and is_available:
                    amount = await self.friend_claim(http_client=http_client)
                    self.success(f"Claimed friend ref reward {amount}")

                if play_passes and play_passes > 0 and settings.PLAY_GAMES is True:
                    await self.play_game(http_client=http_client, play_passes=play_passes)

                #await asyncio.sleep(random.uniform(1, 3))

                try:
                    timestamp, start_time, end_time, play_passes = await self.balance(http_client=http_client)

                    if start_time is None and end_time is None:
                        await self.start(http_client=http_client)
                        self.info(f"<lc>[FARMING]</lc> Start farming!")
                        await asyncio.sleep(1)

                    elif (start_time is not None and end_time is not None and timestamp is not None and
                          timestamp >= end_time):
                        timestamp, balance = await self.claim(http_client=http_client)
                        self.success(f"<lc>[FARMING]</lc> Claimed reward! Balance: {balance}")
                        await asyncio.sleep(1)

                    elif end_time is not None and timestamp is not None:
                        sleep_duration = end_time - timestamp
                        self.info(f"<lc>[FARMING]</lc> Sleep {format_duration(sleep_duration)}")
                        login_need=True
                        await asyncio.sleep(sleep_duration)

                except Exception as e:
                    self.error(f"<lc>[FARMING]</lc> Error in farming management: {e}")

            except InvalidSession as error:
                raise error

            except Exception as error:
                logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Unknown error: {error}")
                await asyncio.sleep(delay=3)


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
