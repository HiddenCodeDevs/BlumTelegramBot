import asyncio
from contextlib import suppress
from argparse import ArgumentParser

from bot.core.registrator import register_sessions
from bot.utils.launcher import get_session_names, get_proxies, start_text, run_tasks
from bot.utils.logger import logger


async def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("-a", "--action", type=int, help="Action to perform")
    print(start_text)
    logger.info(f"Detected {len(get_session_names())} sessions | {len(get_proxies())} proxies")

    action = parser.parse_args().action

    actions = {
        1: run_tasks,
        2: register_sessions
    }

    if not action:
        print(f"Select an action:\n    1. Run clicker\n    2. Create session")
        while True:
            action = input("> ")
            if not action.isdigit():
                logger.warning("<red>Action must be number</red>")
            elif int(action) not in actions:
                logger.warning("<red>Action must be <cyan>1</cyan> or <cyan>2</cyan></red>")
            else:
                action = int(action)
                break

    await actions[action]()

if __name__ == '__main__':
    try:
        with suppress(KeyboardInterrupt):
            asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except BaseException as e:
        raise BaseException
