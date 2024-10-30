from aiohttp import ClientSession
from bot.utils.logger import SessionLogger

class BlumApi:

    game_url = "https://game-domain.blum.codes"
    earn_domain = "https://earn-domain.blum.codes"
    user_url = "https://user-domain.blum.codes"
    tribe_url = "https://tribe-domain.blum.codes"

    _session: ClientSession
    _log: SessionLogger

    def __init__(self, logger: SessionLogger):
        self._log = SessionLogger("API |" + logger.session_name)


    def set_session(self, http_client: ClientSession):
        self._session = http_client

    async def auth(self, init_data):
        await self._session.options(url=f'{self.user_url}/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP')
        resp = await self._session.post(url=f"{self.user_url}/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP", json=init_data)
        if resp.status == 520:
            self._log.warning('Need re-login!')
            return False
        resp_json = await resp.json()
        return resp_json

    async def get_new_auth_tokens(self, refresh_token):
        if "Authorization" in self._session.headers:
            del self._session.headers["Authorization"]
        json_data = {'refresh': refresh_token}
        resp = await self._session.post(f"{self.user_url}/api/v1/auth/refresh", json=json_data, ssl=False)
        resp_json = await resp.json()
        return resp_json.get('access'), resp_json.get('refresh')

    async def balance(self) -> dict | None:
        try:
            resp = await self._session.get(f"{self.game_url}/api/v1/user/balance")
            data: dict = await resp.json()

            is_normal = True
            for key in ["availableBalance", "playPasses", "isFastFarmingEnabled", "timestamp", "farming"]:
                if key not in data:
                    is_normal = False
            if is_normal:
                return data
            self._log.error("Unknown balance structure, need update api")
        except Exception as e:
            self._log.error(f"Error occurred during balance: {e}")

    async def daily_reward_is_available(self) -> str | None:
        try:
            resp = await self._session.get(f"{self.game_url}/api/v1/daily-reward?offset=-180")
            data = await resp.json()
            if data.get("message") == "Not Found":
                return
            days = data.get("days")
            if days:
                current_reward: dict = days[-1].get("reward")
                return f"passes: {current_reward.get('passes')}, BP: {current_reward.get('points')}"
            raise BaseException(f"need update daily_reward_is_available. response: {data}")
        except Exception as e:
            self._log.error(f"Error occurred during claim daily reward: {e}")

    async def claim_daily_reward(self) -> bool:
        try:
            resp = await self._session.post(f"{self.game_url}/api/v1/daily-reward?offset=-180")
            txt = await resp.text()
            print(resp.status, txt)
            if resp.status == 200:
                return True

            # return True if txt == 'OK' else txt
            raise BaseException(f"need update claim_daily_reward. response: {txt}")
        except Exception as e:
            self._log.error(f"Error occurred during claim daily reward: {e}")
        return False


    async def elig_dogs(self):
        try:
            resp = await self._session.get(f'{self.game_url}/api/v2/game/eligibility/dogs_drop')
            data = await resp.json()
            if resp.status == 200:
                return data.get('eligible', False)
            raise Exception(f"Unknown eligibility status: {data}")
        except Exception as e:
            self._log.error(f"Failed elif dogs, error: {e}")
        return None

    async def start_game(self):
        try:
            resp = await self._session.post(f"{self.game_url}/api/v2/game/play")
            # {'gameId': '38cb2ed0-1978-4239-b0c1-f6dc5edf95cf', 'assets': {'BOMB': {'probability': '0.03', 'perClick': '1'}, 'CLOVER': {'probability': '0.95', 'perClick': '1'}, 'FREEZE': {'probability': '0.02', 'perClick': '1'}}}
            response_data = await resp.json()
            return response_data.get("gameId")

            # elif "message" in response_data:
            #     return response_data.get("message")
        except Exception as e:
            self._log.error(f"Error occurred during start game: {e}")

    async def claim_game(self, payload: str) -> bool:
        try:
            resp = await self._session.post(f"{self.game_url}/api/v2/game/claim", json={"payload": payload})
            txt = await resp.text()
            if resp.status != 200:
                self._log.error(f"error claim_game: {txt}")
            return True if txt == 'OK' else False
        except Exception as e:
            self._log.error(f"Error occurred during claim game: {e}")

    async def get_tasks(self):
        try:
            resp = await self._session.get(f'{self.earn_domain}/api/v1/tasks')
            if resp.status not in [200, 201]:
                return None
            resp_json = await resp.json()
            return resp_json
        except Exception as error:
            self._log.error(f"Start complete error {error}")

    async def start_task(self, task_id):
        try:
            resp = await self._session.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/start')

        except Exception as error:
            self._log.error(f"Start complete error {error}")

    async def validate_task(self, task_id, keyword: str) -> bool:
        try:
            payload = {'keyword': keyword}
            resp = await self._session.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/validate', json=payload)
            resp_json = await resp.json()
            if resp_json.get('status') == "READY_FOR_CLAIM":
                return True
            if resp_json.get('message') == "Incorrect task keyword":
                return False
            self._log.error(f"validate_task error: {resp_json}")
        except Exception as error:
            self._log.error(f"Start complete error {error}")

    async def claim_task(self, task_id):
        try:
            resp = await self._session.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/claim')
            resp_json = await resp.json()
            if resp_json.get('status') == "FINISHED":
                return True
            self._log.error(f"claim_task error: {resp_json}")
        except Exception as error:
            self._log.error(f"Claim task error {error}")

    async def start_farming(self):
        try:
            resp = await self._session.post(f"{self.game_url}/api/v1/farming/start")
            data = await resp.json()

            if resp.status != 200:
                self._log.error("Failed start farming")
            return data
        except Exception as e:
            self._log.error(f"Error occurred during start: {e}")

    async def claim_farm(self) -> bool | None:
        try:
            resp = await self._session.post(f"{self.game_url}/api/v1/farming/claim")
            resp_json = await resp.json()
            # {'availableBalance': '1.1', 'playPasses': 1, 'isFastFarmingEnabled': True, 'timestamp': 111}
            for key in ['availableBalance', 'playPasses', 'isFastFarmingEnabled', 'timestamp']:
                if key not in resp_json:
                    raise Exception(f"Unknown structure claim_farm result: {resp_json}")
            return True
        except Exception as e:
            self._log.error(f"Error occurred during claim: {e}")


    async def get_friends_balance(self) -> dict | None:
        try:
            resp = await self._session.get(f"{self.user_url}/api/v1/friends/balance")

            resp_json = await resp.json()
            if resp.status != 200:
                raise Exception(f"error from get friends balance: {resp_json}")
            return resp_json
        except Exception as e:
            self._log.error(f"Error occurred during friend balance: {e}")

    async def claim_friends_balance(self):
        try:
            resp = await self._session.post(f"{self.user_url}/api/v1/friends/claim")
            resp_json = await resp.json()
            print("claim_friends_balance", resp_json)
            amount = resp_json.get("claimBalance")
            if resp.status != 200:
                raise Exception(f"Failed claim_friends_balance: {resp_json}")
            return amount
        except Exception as e:
            self._log.error(f"Error occurred during friends claim: {e}")


    async def search_tribe(self, chat_name):
        if not chat_name:
            return
        try:
            resp = await self._session.get(f'{self.tribe_url}/api/v1/tribe?search={chat_name}')
            resp_json = await resp.json()
            if resp.status != 200:
                raise Exception(f"Failed search_tribe: {resp_json}")
            result = resp_json.get("items")
            if result:
                return result.pop(0)

        except Exception as e:
            self._log.error(f"Error occurred during friends claim: {e}")

    async def get_tribe_info(self, chat_name):
        try:
            resp = await self._session.get(f'{self.tribe_url}/api/v1/tribe/by-chatname/{chat_name}')
            resp_json = await resp.json()
            if resp.status == 200:
                return resp_json
            raise Exception(f"Failed get_tribe_info: {resp_json}")
        except Exception as e:
            self._log.error(f"Error occurred during friends claim: {e}")

    async def get_my_tribe(self):
        try:
            resp = await self._session.get(f'{self.tribe_url}/api/v1/tribe/my')
            resp_json = await resp.json()
            if resp.status == 404 and resp_json.get("data"):
                return resp_json.get("data")
            if resp.status == 200 and resp_json.get("chatname"):
                return resp_json
            raise Exception(f"Failed get_my_tribe: {resp_json}")

        except Exception as e:
            self._log.error(f"Error occurred during friends claim: {e}")

    async def leave_tribe(self):
        try:
            resp = await self._session.post(f'{self.tribe_url}/api/v1/tribe/leave', json={})
            text = await resp.text()
            if text == 'OK':
                return True
            raise Exception(f"Failed leave_tribe: {text}")
        except Exception as e:
            self._log.error(f"Error occurred during friends claim: {e}")

    async def join_tribe(self, tribe_id):
        try:
            resp = await self._session.post(f'{self.tribe_url}/api/v1/tribe/{tribe_id}/join', json={})
            text = await resp.text()
            if text == 'OK':
                return True
            raise Exception(f"Failed join_tribe: {text}")
        except Exception as e:
            self._log.error(f"Error occurred during friends claim: {e}")