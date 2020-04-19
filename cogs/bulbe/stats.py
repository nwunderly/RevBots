import discord
from discord.ext import commands

"""

2.1.5 -> fix logging, configurable permissions
      -> LEAVE THIS OUT OF THIS GIT PUSH

2.2.0 -> implement stats tracking (guild invite tracking and command stats)

"""


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        pass


def setup(bot):
    bot.add_cog(Stats(bot))
