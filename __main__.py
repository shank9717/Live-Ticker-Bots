import asyncio
import configparser
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from discord import Intents
from discord.ext import commands

import constants

config = configparser.ConfigParser()


def setup() -> None:
    logging.basicConfig(format='{asctime}:{levelname}:{name}:{message}',
                        datefmt='%d-%m-%Y %H:%M:%S', level=logging.INFO,
                        handlers=[logging.StreamHandler(),
                                  RotatingFileHandler('./log', mode='a', maxBytes=1 * 1024 * 1024,
                                                      backupCount=2, encoding=None, delay=0)])
    load_variables()


def load_variables() -> None:
    with open(constants.CONFIG_FILE_PATH + constants.CONFIG_FILE_NAME, 'r', encoding='utf-8') as f:
        properties = f.read()
    config.read_string(properties)


def no_dm_check(ctx: commands.Context) -> bool:
    if ctx.guild is None:
        raise commands.NoPrivateMessage('Private messages not permitted.')
    return True


async def main():
    setup()
    token = config.get('TickerDetails', 'auth_token')

    intents = Intents.default()
    intents.members = True
    bot: commands.Bot = commands.Bot(command_prefix='#-#', intents=intents)
    bot.config: configparser.ConfigParser = config

    async with bot:
        cogs = [file.stem for file in Path('cogs').glob('*.py')]
        for extension in cogs:
            await bot.load_extension(f'cogs.{extension}')
        logging.info(f'Cogs loaded: {", ".join(bot.cogs)}')

        # Restrict bot usage to inside guild channels only.
        bot.add_check(no_dm_check)
        await bot.start(token)


if __name__ == '__main__':
    asyncio.run(main())
