
import discord
from discord.ext import commands

from typing import Union, Optional

from utils.converters import FetchedUser
from utils.utility import red_tick


class DevTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def oauth(self, ctx, bot: Union[discord.User, FetchedUser], *perms):
        """Generates an invite link for a bot with the requested perms."""
        if not bot.bot:
            await ctx.send(f"{red_tick} `{bot}` isn't a bot!")
            return
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
        await ctx.send(f"Invite link for `{bot}`:\n"+link)

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
            await ctx.send(desc)

    class FindIDArgs(commands.Converter):
        async def convert(self, ctx, argument):
            if argument == 'guild':
                return ctx.guild
            elif argument == 'channel':
                return ctx.channel
            elif argument == 'me':
                return ctx.author
            else:
                raise commands.BadArgument

    @commands.group(name='id')
    async def find_id(self, ctx, *, target: Union[FindIDArgs, discord.TextChannel, discord.VoiceChannel, discord.Role, discord.Member, discord.User, discord.PartialEmoji]):
        """Attempts to convert your query to a discord object and returns its id.
        Search order: Special args, TextChannel, VoiceChannel, Role, Member, User, Emoji.
        Special args: 'guild', 'channel', 'me'"""
        await ctx.send(f"`{(type(target)).__name__}` **{target.name}**:  `{target.id}`")

    @find_id.error
    async def find_id_error(self, ctx, error):
        if isinstance(error, commands.UserInputError):
            await ctx.send("Could not locate a snowflake based on that query.")

    async def channel(self, ctx, *, target):
        pass

    async def role(self, ctx, *, target):
        pass

    async def member(self, ctx, *, target):
        pass

    async def user(self, ctx, *, target):
        pass


def setup(bot):
    bot.add_cog(DevTools(bot))
