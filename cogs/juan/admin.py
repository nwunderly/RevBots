
import psutil
import asyncio
import datetime

import discord
from discord.ext import commands

from utils import checks
from utils import converters


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        pass

    @commands.command()
    async def test(self, ctx):
        await ctx.send(f"Online and functional. <:juandissimo:570424731501723648>\n"
                       f"Online for: {datetime.datetime.now() - self.bot.started_at}\n"
                       f"Cogs: {', '.join(list(self.bot.cogs.keys()))}")

    @commands.command()
    async def close(self, ctx):
        await ctx.send("Closing.")
        await self.bot.close()


def setup(bot):
    bot.add_cog(Admin(bot))
