import argparse
import distutils.util
import logging
from logging.handlers import TimedRotatingFileHandler
from os import environ
from pathlib import Path

from discord import Intents
from discord.ext import commands



def setup():
    logging.basicConfig(format='{asctime}:{levelname}:{name}:{message}', style='{',
                        datefmt='%d-%m-%Y %H:%M:%S', level=logging.INFO,
                        handlers=[logging.StreamHandler(),
                                  TimedRotatingFileHandler('./log', when='D',
                                                           backupCount=3, utc=True)])


def main():
    parser = argparse.ArgumentParser()

    token = environ.get('BOT_TOKEN')
    if not token:
        token = 'ODQ1OTU2MTc5MTA4MDM2NjA5.YKogFg._rPVY5bJc2Uwa06XQtDt-VEN3oY'

    allow_self_register = environ.get('ALLOW_DUEL_SELF_REGISTER')
    if allow_self_register:
        ALLOW_DUEL_SELF_REGISTER = bool(distutils.util.strtobool(allow_self_register))

    setup()

    intents = Intents.default()
    intents.members = True
    bot = commands.Bot(command_prefix='.', intents=intents)
    cogs = [file.stem for file in Path('cogs').glob('*.py')]
    for extension in cogs:
        bot.load_extension(f'cogs.{extension}')
    logging.info(f'Cogs loaded: {", ".join(bot.cogs)}')

    def no_dm_check(ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage('Private messages not permitted.')
        return True

    # Restrict bot usage to inside guild channels only.
    bot.add_check(no_dm_check)

    bot.run(token)


if __name__ == '__main__':
    main()
