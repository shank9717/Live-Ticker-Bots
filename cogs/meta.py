from discord.ext import commands

from discord.ext import tasks
from discord import Activity, ActivityType

import cogs.Stats.tv_helper as tv_helper
import logging
import asyncio
from threading import Thread
from queue import LifoQueue

class MetaHelpers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_thread = None
        self.queue = LifoQueue()
        self.bot.add_listener(self.start_update, 'on_ready')

    @tasks.loop(seconds=2.0)
    async def update_values(self):
        try:
            if not self.queue.empty():
                check_data = self.queue.get()
                while not self.queue.empty():
                    try:
                        self.queue.get()
                    except Exception as e:
                        logging.error(e)
                        continue
            else:
                check_data = ['##RELOAD##']
            if check_data[0] == '##RELOAD##':
                try:
                    self.current_thread.join()
                except:
                    await asyncio.sleep(120)
                    pass
                self.current_thread = tv_helper.StocksApi('in1!', self.queue)
                self.current_thread.start()
                return

            ltp, currency, cv, cvp = check_data
        except Exception as e:
            logging.error(e)
            return
        
        ltp = round(float(ltp), 2)
        sign = '⬈' if float(cv) > 0 else '⬊'
        direction = '' if float(cv) < 0 else '+'
        currency = '$'

        current_value = 'SGX {} {}'
        current_value = current_value.format(sign, '{} {}'.format(currency, ltp))

        change_value = '{}{} ({}%)'.format(direction, cv, cvp)
        logging.debug("Updating values: " + str(ltp) + ", " + change_value)

        unique_guilds = []
        for channel in self.bot.get_all_channels():
            unique_guilds.append(channel.guild)
        
        for guild in set(unique_guilds):
            member = guild.get_member(self.bot.user.id)
            try:
                await member.edit(nick=current_value)
                await self.bot.change_presence(activity=Activity(type=ActivityType.playing, name=change_value))
                await self.set_colors(member, guild, sign)
            except:
                return


        logging.info("Updated values")

    async def start_update(self):
        self.update_values.start()
        self.current_thread = tv_helper.StocksApi('in1!', self.queue)
        self.current_thread.start()

    async def set_colors(self, member, guild, sign):
        if not member.guild_permissions.manage_roles:
            return
        ticker_red_role = None
        ticker_green_role = None
        for role in guild.roles:
            if role.name == 'ticker-red':
                ticker_red_role = role
            elif role.name == 'ticker-green':
                ticker_green_role = role
        
        if (ticker_green_role != None and ticker_red_role != None):
            try:
                if (sign == '⬈'):
                    await member.remove_roles(ticker_red_role)
                    await member.add_roles(ticker_green_role)
                else:
                    await member.add_roles(ticker_red_role)
                    await member.remove_roles(ticker_green_role)
            except Exception as e:
                logging.error(e)

def setup(bot):
    bot.add_cog(MetaHelpers(bot))
