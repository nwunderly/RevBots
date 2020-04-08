
import discord
from discord.ext import commands

from typing import Union, Optional

from utils.converters import FetchedUser


class DevTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def oauth(self, ctx, bot: Union[discord.User, FetchedUser], *perms):
        """Generates an invite link for a bot with the requested perms."""
        if perms:
            p = None
            if len(perms) == 1:
                try:
                    p = discord.Permissions(int(perms[0]))
                except ValueError:
                    pass
            if not p:
                kwargs = {}
                for perm in perms:
                    kwargs[perm] = True
                try:
                    p = discord.Permissions(**kwargs)
                except TypeError as e:
                    await ctx.send(str(e))
                    return
        else:
            p = None
        link = discord.utils.oauth_url(bot.id, permissions=p)
        link = '<' + link + '>'
        embed = self.bot.Embed(description=link)
        await ctx.send(link)

    @commands.command()
    async def oauthperms(self, ctx, *perms):
        """Converts permissions integer to list of permissions, and vice-versa."""
        try:
            value = int(perms[0])
            p = discord.Permissions(value)
        except ValueError:
            p = None
            value = None
        if p:
            # int conversion worked, send list of perms
            desc = f"Permissions integer `{value}` will grant these perms: \n"
            desc += "".join([("- " + perm + "\n") for perm, val in p if val])
            embed = self.bot.Embed(description=desc)
            await ctx.send(desc)
            return
        else:
            # use list of perms
            kwargs = {}
            for perm in perms:
                kwargs[perm] = True
            try:
                p = discord.Permissions(**kwargs)
            except TypeError as e:
                await ctx.send(e)
                return
            desc = f"These permissions will have permissions integer `{p.value}`"
            embed = self.bot.Embed(description=desc)
            await ctx.send(desc)


def setup(bot):
    bot.add_cog(DevTools(bot))