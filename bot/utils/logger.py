import sys
from bot.config import settings
from typing import Callable

from loguru import logger

logger.remove()

level = "DEBUG" if settings.DEBUG else "INFO"

logger.add(sink=sys.stdout, level=level, format="<light-white>{time:YYYY-MM-DD HH:mm:ss}</light-white>"
                                   " | <level>{level}</level>"
                                   " | <light-white><b>{message}</b></light-white>")

logger.add("blum_dev.log", level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", rotation="20 MB")

logger = logger.opt(colors=True)

MessageMethod = Callable[[str], None]

def disable_color_on_error(formatter, level_):
    def wrapper(*args, **kwargs):
        try:
            getattr(logger, level_)(formatter(*args, **kwargs))
        except ValueError:
            getattr(logger.opt(colors=False), level)(*args, **kwargs)
    return wrapper

class SessionLogger:

    session_name: str
    trace: MessageMethod
    debug: MessageMethod
    info: MessageMethod
    success: MessageMethod
    warning: MessageMethod
    error: MessageMethod
    critical: MessageMethod

    def __init__(self, session_name):
        self.session_name = session_name
        for method_name in ("trace", "debug", "info", "success", "warning", "error", "critical"):
            setattr(self, method_name, disable_color_on_error(self._format, method_name))

    def _format(self, message):
        return f"{self.session_name} | {message}"
