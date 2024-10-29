from aiohttp import ClientSession
from bot.utils.logger import SessionLogger

class BlumApi:

    game_url = "https://game-domain.blum.codes"
    earn_domain = "https://earn-domain.blum.codes"
    user_url = "https://user-domain.blum.codes"

    _session: ClientSession
    _log: SessionLogger

    def __init__(self, logger: SessionLogger):
        self._log = logger


    def set_session(self, http_client: ClientSession):
        self._session = http_client

    async def balance(self):
        try:
            resp = await self._session.get(f"{self.game_url}/api/v1/user/balance", ssl=False)
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
            self._log.error(f"Error occurred during balance: {e}")

    async def claim_daily_reward(self):
        try:
            resp = await self._session.post(f"{self.game_url}/api/v1/daily-reward?offset=-180", ssl=False)
            txt = await resp.text()
            return True if txt == 'OK' else txt
        except Exception as e:
            self._log.error(f"Error occurred during claim daily reward: {e}")


    async def elig_dogs(self):
        try:
            resp = await self._session.get(f'https://{self.game_url}/api/v2/game/eligibility/dogs_drop')
            if resp is not None:
                data = await resp.json()
                eligible = data.get('eligible', False)
                return eligible

        except Exception as e:
            self._log.error(f"Failed elif dogs, error: {e}")
        return None

    async def start_game(self):
        try:
            resp = await self._session.post(f"{self.game_url}/api/v2/game/play", ssl=False)
            response_data = await resp.json()
            self._log.debug(f"start_game. {response_data}")
            return response_data.get("gameId")

            # elif "message" in response_data:
            #     return response_data.get("message")
        except Exception as e:
            self._log.error(f"Error occurred during start game: {e}")

    async def claim_game(self, payload: str) -> bool:
        try:
            resp = await self._session.post(f"{self.game_url}/api/v2/game/claim", json={"payload": payload}, ssl=False)
            txt = await resp.text()
            if resp.status != 200:
                self._log.error(f"error claim_game: {txt}")
            return True if txt == 'OK' else False
        except Exception as e:
            self._log.error(f"Error occurred during claim game: {e}")

    async def get_tasks(self):
        try:
            resp = await self._session.get(f'{self.earn_domain}/api/v1/tasks', ssl=False)
            if resp.status not in [200, 201]:
                return None
            resp_json = await resp.json()
            return resp_json
        except Exception as error:
            self._log.error(f"Start complete error {error}")

    async def start_task(self, task_id):
        try:
            resp = await self._session.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/start',
                                          ssl=False)

        except Exception as error:
            self._log.error(f"Start complete error {error}")

    async def validate_task(self, task_id, keyword: str) -> bool:
        try:
            payload = {'keyword': keyword}

            resp = await self._session.post(
                f'{self.earn_domain}/api/v1/tasks/{task_id}/validate',
                json=payload, ssl=False
            )
            resp_json = await resp.json()
            if resp_json.get('status') == "READY_FOR_CLAIM":
                return True
        except Exception as error:
            self._log.error(f"Start complete error {error}")
        return False

    async def claim_task(self, task_id):
        try:
            resp = await self._session.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/claim',
                                          ssl=False)
            resp_json = await resp.json()

            return resp_json.get('status') == "FINISHED"
        except Exception as error:
            self._log.error(f"Claim task error {error}")

    async def start_farming(self):
        try:
            resp = await self._session.post(f"{self.game_url}/api/v1/farming/start", ssl=False)

            if resp.status != 200:
                self._log.error("Failed start farming")
        except Exception as e:
            self._log.error(f"Error occurred during start: {e}")

    async def claim_farm(self):
        try:
            resp = await self._session.post(f"{self.game_url}/api/v1/farming/claim", ssl=False)
            if resp.status not in [200, 201]:
                return None
            resp_json = await resp.json()
            return int(resp_json.get("timestamp") / 1000), resp_json.get("availableBalance")

        except Exception as e:
            self._log.error(f"Error occurred during claim: {e}")


    async def friend_balance(self):
        try:
            while True:
                resp = await self._session.get(f"{self.user_url}/api/v1/friends/balance", ssl=False)
                if resp.status not in [200, 201]:
                    return 0, False
                else:
                    break
            resp_json = await resp.json()
            claim_amount = resp_json.get("amountForClaim")
            is_available = resp_json.get("canClaim")

            return (claim_amount,
                    is_available)
        except Exception as e:
            self._log.error(f"Error occurred during friend balance: {e}")

    async def friend_claim(self):
        try:

            resp = await self._session.post(f"{self.user_url}/api/v1/friends/claim", ssl=False)
            resp_json = await resp.json()
            amount = resp_json.get("claimBalance")
            if resp.status != 200:
                resp = await self._session.post(f"{self.user_url}/api/v1/friends/claim", ssl=False)
                resp_json = await resp.json()
                amount = resp_json.get("claimBalance")

            return amount
        except Exception as e:
            self._log.error(f"Error occurred during friends claim: {e}")

