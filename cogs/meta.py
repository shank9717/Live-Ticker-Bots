from discord.ext import commands

from discord.ext import tasks
from discord import Activity, ActivityType

import cogs.Stats.tv_helper as tv_helper
import logging
from threading import Thread

class MetaHelpers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_listener(self.start_update, 'on_ready')

    @tasks.loop(seconds=2.0)
    async def update_values(self):
        try:
            with open('data.txt', 'r') as f:
                check_data = f.readlines()

            if (check_data[0]) == '##RELOAD##\n':
                with open('data.txt', 'w') as f:
                    print("", file=f, flush=True)
                thread = Thread(target=tv_helper.main, args=('in1!', {}))
                thread.start()
                return
            ltp, currency, cv, cvp = [ticker_data[:-1] for ticker_data in check_data]
        except:
            return
        
        ltp = round(float(ltp), 2)
        sign = '⬈' if float(cv) > 0 else '⬊'
        direction = '' if float(cv) < 0 else '+'
        currency = '$'

        current_value = 'SGX {} {}'
        current_value = current_value.format(sign, '{} {}'.format(currency, ltp))

        change_value = '{}{} ({}%)'.format(direction, cv, cvp)
        logging.info("Updating values: " + str(ltp) + ", " + change_value)

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
        with open('data.txt', 'w') as f:
            print("", file=f, flush=True)
        self.update_values.start()
        thread = Thread(target=tv_helper.main, args=('in1!', {}))
        thread.start()

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
