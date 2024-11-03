from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_PATH = ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    PLAY_GAMES: bool = True
    POINTS: list[int] = [190, 230]
    USE_CUSTOM_PAYLOAD_SERVER: bool = True
    CUSTOM_PAYLOAD_SERVER_URL: str = "http://localhost:9876"

    AUTO_TASKS: bool = True

    USE_RANDOM_DELAY_IN_RUN: bool = True
    RANDOM_DELAY_IN_RUN: list[int] = [5, 30]

    USE_REF: bool = False
    REF_ID: str = ''

    TRIBE_CHAT_TAG: str = 'hidden_coding'

    USE_PROXY_FROM_FILE: bool = False

    DEBUG: bool = False
    SLEEP_MINUTES_BEFORE_ITERATIONS: list[int] = [120, 600]

try:
    settings = Settings()
except ValidationError as error:
    print("ERRORS from .env file!")
    for e in error.errors():
        print(f"[{e['type']} error] Field: \"{' '.join(e['loc'])}\". Message: {e['msg']}")
    exit(1)

