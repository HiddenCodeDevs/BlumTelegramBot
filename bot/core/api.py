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

    async def get(self, url: str):
        await self._session.options(url=url, ssl=False)
        return await self._session.get(url=url, ssl=False)

    async def post(self, url: str, data: dict = None):
        await self._session.options(url=url, ssl=False)
        return await self._session.post(url=url, json=data, ssl=False)

    @staticmethod
    def error_wrapper(method):
        async def wrapper(self, *arg, **kwargs):
            try:
                return await method(self, *arg, **kwargs)
            except Exception as e:
                self._log.error(f"Error on BlumApi.{method.__name__} | {type(e).__name__}: {e}")
        return wrapper


    async def auth(self, init_data):
        resp = await self.post(url=f"{self.user_url}/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP", data=init_data)
        if resp.status == 520:
            self._log.warning('Need re-login!')
            return False
        resp_json = await resp.json()
        return resp_json

    async def get_new_auth_tokens(self, refresh_token):
        if "Authorization" in self._session.headers:
            del self._session.headers["Authorization"]
        json_data = {'refresh': refresh_token}
        resp = await self.post(f"{self.user_url}/api/v1/auth/refresh", data=json_data)
        resp_json = await resp.json()
        return resp_json.get('access'), resp_json.get('refresh')

    @error_wrapper
    async def balance(self) -> dict | None:
        resp = await self.get(f"{self.game_url}/api/v1/user/balance")
        data = await resp.json()

        is_normal = True
        for key in ["availableBalance", "playPasses", "isFastFarmingEnabled", "timestamp", "farming", "isFastFarmingEnabled"]:
            if key not in data:
                is_normal = False
        if is_normal:
            return data
        self._log.error(f"Unknown balance structure. status: {resp.status}, body: {data}")

    @error_wrapper
    async def daily_reward_is_available(self) -> str | None:
        resp = await self.get(f"{self.game_url}/api/v1/daily-reward?offset=-180")
        data = await resp.json()
        if data.get("message") == "Not Found":
            return
        days = data.get("days")
        if days:
            current_reward: dict = days[-1].get("reward")
            return f"passes: {current_reward.get('passes')}, BP: {current_reward.get('points')}"
        raise BaseException(f"need update daily_reward_is_available. response: {data}")

    @error_wrapper
    async def claim_daily_reward(self) -> bool:
        resp = await self.post(f"{self.game_url}/api/v1/daily-reward?offset=-180")
        txt = await resp.text()
        if resp.status == 200 and txt == "OK":
            return True
        raise BaseException(f"error struct, need update. response status {resp.status}, body: {txt}")

    @error_wrapper
    async def elig_dogs(self):
        resp = await self.get(f'{self.game_url}/api/v2/game/eligibility/dogs_drop')
        data = await resp.json()
        if resp.status == 200:
            return data.get('eligible', False)
        raise Exception(f"Unknown eligibility status: {data}")

    @error_wrapper
    async def start_game(self):
        resp = await self.post(f"{self.game_url}/api/v2/game/play")
        # {'gameId': '38cb2ed0-1978-4239-b0c1-f6dc5edf95cf', 'assets': {'BOMB': {'probability': '0.03', 'perClick': '1'}, 'CLOVER': {'probability': '0.95', 'perClick': '1'}, 'FREEZE': {'probability': '0.02', 'perClick': '1'}}}
        response_data = await resp.json()
        return response_data.get("gameId")

    @error_wrapper
    async def claim_game(self, payload: str) -> bool:
        resp = await self.post(f"{self.game_url}/api/v2/game/claim", data={"payload": payload})
        txt = await resp.text()
        if resp.status != 200:
            self._log.error(f"error claim_game. response status {resp.status}: {txt}")
        return True if txt == 'OK' else False

    @error_wrapper
    async def get_tasks(self):
        resp = await self.get(f'{self.earn_domain}/api/v1/tasks')
        if resp.status not in [200, 201]:
            return None
        resp_json = await resp.json()
        return resp_json

    @error_wrapper
    async def start_task(self, task_id):
        resp = await self.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/start')
        resp_json = await resp.json()
        if resp_json.get("status") == 'STARTED':
            return True
        raise Exception(f"unknown response structure. status: {resp.status}. body: {resp_json}")

    @error_wrapper
    async def validate_task(self, task_id, keyword: str) -> bool:
        payload = {'keyword': keyword}
        resp = await self.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/validate', data=payload)
        resp_json = await resp.json()
        if resp_json.get('status') == "READY_FOR_CLAIM":
            return True
        if resp_json.get('message') == "Incorrect task keyword":
            return False
        self._log.error(f"validate_task error: {resp_json}")

    @error_wrapper
    async def claim_task(self, task_id):
        resp = await self.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/claim')
        resp_json = await resp.json()
        if resp_json.get('status') == "FINISHED":
            return True
        self._log.error(f"claim_task error: {resp_json}")

    @error_wrapper
    async def start_farming(self):
        resp = await self.post(f"{self.game_url}/api/v1/farming/start")
        data = await resp.json()

        if resp.status != 200:
            self._log.error("Failed start farming")
        return data

    @error_wrapper
    async def claim_farm(self) -> bool | None:
        resp = await self.post(f"{self.game_url}/api/v1/farming/claim")
        resp_json = await resp.json()
        # {'availableBalance': '1.1', 'playPasses': 1, 'isFastFarmingEnabled': True, 'timestamp': 111}
        for key in ['availableBalance', 'playPasses', 'isFastFarmingEnabled', 'timestamp']:
            if key not in resp_json:
                raise Exception(f"Unknown structure claim_farm result: {resp_json}")
        return True

    @error_wrapper
    async def get_friends_balance(self) -> dict | None:
        resp = await self.get(f"{self.user_url}/api/v1/friends/balance")

        resp_json = await resp.json()
        if resp.status != 200:
            raise Exception(f"error from get friends balance: {resp_json}")
        return resp_json

    @error_wrapper
    async def claim_friends_balance(self):
        resp = await self.post(f"{self.user_url}/api/v1/friends/claim")
        resp_json = await resp.json()
        if resp.status != 200:
            raise Exception(f"Failed claim_friends_balance: {resp_json}")
        return resp_json.get("claimBalance")

    @error_wrapper
    async def search_tribe(self, chat_name):
        if not chat_name:
            return
        resp = await self.get(f'{self.tribe_url}/api/v1/tribe?search={chat_name}')
        resp_json = await resp.json()
        if resp.status != 200:
            raise Exception(f"Failed search_tribe: {resp_json}")
        result = resp_json.get("items")
        if result:
            return result.pop(0)

    @error_wrapper
    async def get_tribe_info(self, chat_name):
        resp = await self.get(f'{self.tribe_url}/api/v1/tribe/by-chatname/{chat_name}')
        resp_json = await resp.json()
        if resp.status == 200:
            return resp_json
        raise Exception(f"Failed get_tribe_info: {resp_json}")

    @error_wrapper
    async def get_my_tribe(self):
        resp = await self.get(f'{self.tribe_url}/api/v1/tribe/my')
        resp_json = await resp.json()
        if resp.status == 404 and resp_json.get("data"):
            return resp_json.get("data")
        if resp.status == 424:
            resp_json.update({"blum_bug": True})  # if return 424 blum not loaded tribes
            return resp_json
        if resp.status == 200 and resp_json.get("chatname"):
            return resp_json
        raise Exception(f"Unknown structure. status {resp.status}, body: {resp_json}")

    @error_wrapper
    async def leave_tribe(self):
        resp = await self.post(f'{self.tribe_url}/api/v1/tribe/leave', data={})
        text = await resp.text()
        if text == 'OK':
            return True
        raise Exception(f"Failed leave_tribe: {text}")

    @error_wrapper
    async def join_tribe(self, tribe_id):
        resp = await self.post(f'{self.tribe_url}/api/v1/tribe/{tribe_id}/join', data={})
        text = await resp.text()
        if text == 'OK':
            return True
        raise Exception(f"Failed join_tribe: {text}")