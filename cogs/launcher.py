import asyncio
import logging
from queue import Queue
from typing import List, Optional

from discord import Activity, ActivityType
from discord import Guild, Member
from discord.ext import commands
from discord.ext import tasks
from discord.ext.commands import Bot

import cogs.Stats.tv_helper as tv_helper


class Launcher(commands.Cog):
    WAITING_FLAG = '##WAITING##'
    RELOAD_FLAG = '##RELOAD##'

    def __init__(self, bot: Bot):
        self.bot = bot
        self.current_thread: Optional[tv_helper.StocksApi] = None
        self.queue = Queue()
        self.queue.put([self.WAITING_FLAG])
        self.currency: str = self.bot.config.get('TickerDetails', 'currency')
        self.ticker_symbol: str = self.bot.config.get('TickerDetails', 'ticker_symbol')
        self.ticker_nickname: str = self.bot.config.get('TickerDetails', 'ticker_nickname')

        self.bot.add_listener(self.start_update, 'on_ready')

    @tasks.loop(seconds=30)
    async def update_values_loop(self):
        check_data = None
        try:
            if not self.queue.empty():
                check_data = self.queue.get_nowait()
            if check_data is not None and check_data[0] == self.WAITING_FLAG:
                self.queue.put([self.WAITING_FLAG])
                return
            if check_data is not None and check_data[0] == self.RELOAD_FLAG:
                try:
                    self.current_thread.stop()
                except:
                    pass
            if not self.current_thread.is_alive():
                self.current_thread = tv_helper.StocksApi(self.ticker_symbol, self.queue)
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
        direction = '-' if float(cv) < 0 else ''

        current_value = '{} {} {}'
        current_value = current_value.format(self.ticker_nickname, sign, '{} {}'.format(self.currency, ltp))

        change_value = '{}{} ({}%)'.format(direction, cv, cvp)

        unique_guilds: List[Guild] = []
        for channel in self.bot.get_all_channels():
            unique_guilds.append(channel.guild)

        for guild in set(unique_guilds):
            member: Member = guild.get_member(self.bot.user.id)
            try:
                await asyncio.wait_for(member.edit(nick=current_value), timeout=5)
                await asyncio.wait_for(
                    self.bot.change_presence(activity=Activity(type=ActivityType.playing, name=change_value)),
                    timeout=5)
                await asyncio.wait_for(self.set_colors(member, guild, sign), timeout=5)
            except:
                logging.error(f'Couldn\'t update values for guild: {str(guild.name)}')
                return
        logging.info(f'Updated values : {direction}{str(ltp)} / {str(change_value)}')

    async def start_update(self):
        self.current_thread = tv_helper.StocksApi(self.ticker_symbol, self.queue)
        self.current_thread.start()

        while (data := self.queue.get())[0] == self.WAITING_FLAG:
            self.queue.put(data)
        self.queue.put(data)

        self.update_values_loop.start()

    async def set_colors(self, member: Member, guild: Guild, sign: str):
        if not member.guild_permissions.manage_roles:
            logging.warning('No manage role permissions for member in guild: {}'.format(guild.name))
            return
        ticker_red_role = None
        ticker_green_role = None
        for role in guild.roles:
            if role.name == 'ticker-red':
                ticker_red_role = role
            elif role.name == 'ticker-green':
                ticker_green_role = role

        if ticker_green_role is not None and ticker_red_role is not None:
            try:
                current_roles = []
                for role in member.roles:
                    if role.name == 'ticker-red' or role.name == 'ticker-green':
                        current_roles.append(role)

                if sign == '⬈':
                    if ticker_red_role in current_roles:
                        await member.remove_roles(ticker_red_role)
                    if not ticker_green_role in current_roles:
                        await member.add_roles(ticker_green_role)
                else:
                    if ticker_green_role in current_roles:
                        await member.remove_roles(ticker_green_role)
                    if not ticker_red_role in current_roles:
                        await member.add_roles(ticker_red_role)
            except Exception as e:
                logging.error(e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Launcher(bot))
