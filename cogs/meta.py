from discord.ext import commands

from discord.ext import tasks
from discord import Activity, ActivityType
import random

import cogs.Stats.tv_helper as tv_helper
import logging
from threading import Thread

class MetaHelpers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_listener(self.start_update, 'on_ready')

    @tasks.loop(seconds=1.0)
    async def update_values(self):
        try:
            with open('data.txt', 'r') as f:
                ltp, currency, cv, cvp = [ticker_data[:-1] for ticker_data in f.readlines()]
        except:
            return
  
        sign = '+' if float(cv) > 0 else '-'
        currency = '$'

        current_value = 'SGX ({})'
        current_value = current_value.format('{} {}'.format(currency, ltp))

        change_value = '{} ({}%)'.format(cv, cvp)
        logging.info("Updating values")

        await self.bot.change_presence(activity=Activity(type=ActivityType.playing, name=change_value))
        for channel in self.bot.get_all_channels():
            member = channel.guild.get_member(self.bot.user.id)
            await member.edit(nick=current_value)
        logging.info("Updated values")

    async def start_update(self):
        self.update_values.start()
        thread = Thread(target=tv_helper.main, args=('in1!', {}))
        thread.start()

def setup(bot):
    bot.add_cog(MetaHelpers(bot))
