from concurrent.futures import Executor, ThreadPoolExecutor
from http.client import REQUEST_URI_TOO_LONG
from queue import Queue
import time
from typing import List
from discord.ext import commands
from discord.ext.commands import Bot
from discord import Guild, Member
from discord.ext import tasks
from discord import Activity, ActivityType

import cogs.Stats.tv_helper as tv_helper
import logging
import asyncio
from threading import Thread, Event
import multiprocessing

class MetaHelpers(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.current_thread: tv_helper.StocksApi = None
        self.queue = Queue()
        self.queue.put(['##WAITING##'])
        
        self.bot.add_listener(self.start_update, 'on_ready')
    
    
    @tasks.loop(seconds=3)
    async def update_values_loop(self):
        print("Checking")
        check_data = None
        try:
            if not self.queue.empty():
                check_data = self.queue.get_nowait()
            if not check_data is None and check_data[0] == '##WAITING##':
                self.queue.put(['##WAITING##'])
                return
            if not check_data is None and check_data[0] == '##RELOAD##':
                try:
                    self.current_thread.stop()
                except Exception as e:
                    pass
            if not self.current_thread.is_alive():
                self.current_thread = tv_helper.StocksApi('in1!', self.queue)
                self.current_thread.start() 
                return
            if check_data is None:
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

        unique_guilds: List[Guild] = []
        for channel in self.bot.get_all_channels():
            unique_guilds.append(channel.guild)
        
        for guild in set(unique_guilds):
            member: Member = guild.get_member(self.bot.user.id)
            try:
                await asyncio.wait_for(member.edit(nick=current_value), timeout=5)
                await asyncio.wait_for(self.bot.change_presence(activity=Activity(type=ActivityType.playing, name=change_value)), timeout=5)
                await asyncio.wait_for(self.set_colors(member, guild, sign), timeout=5)
            except Exception as e:
                print(e)
                REQUEST_URI_TOO_LONG
        logging.info("Updated values")
        return

    async def start_update(self):
        self.current_thread = tv_helper.StocksApi('in1!', self.queue)
        self.current_thread.start()
        
        while (data := self.queue.get())[0] == '##WAITING##':
            self.queue.put(data)
        self.queue.put(data)

        self.update_values_loop.start()

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
