
import discord
from discord.ext import commands

import typing

from utils import juan_checks as checks
from utils import db


class FanClub(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.table = self.bot.table

    def get_bots(self, user_id):
        return self.table.get([user_id, 'devData'])['bots']

    def register_bot(self, user_id, bot_data):
        try:
            current_data = self.get_bots(user_id)
        except:
            current_data = None
        bots = current_data + [bot_data]
        data = {
            'snowflake': user_id,
            'dataType': 'devData',
            'bots': bots
        }
        self.bot.table.put(data)

    @commands.Cog.listener()
    async def on_member_join(self, message):
        pass

    @commands.command()
    async def bots(self, ctx, who: discord.Member = None):
        who = who if who else ctx.author
        bots = self.get_bots(who.id)
        await ctx.send(bots)

    @commands.command()
    @checks.is_admin()
    async def forceregister(self, ctx, owner_id: int, bot_id: int, prefix):
        try:
            data = {
                'id': bot_id,
                'prefix': prefix
            }
            self.register_bot(owner_id, data)
        except Exception as e:
            await ctx.send(str(e))


def setup(bot):
    bot.add_cog(FanClub(bot))
