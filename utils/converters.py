import discord
from discord.ext import commands

# todo
#   GlobalChannel, GlobalGuild
#


class FetchedUser(commands.Converter):
    async def convert(self, ctx, argument):
        if not argument.isdigit():
            raise commands.BadArgument('Not a valid user ID.')
        try:
            return await ctx.bot.fetch_user(argument)
        except discord.NotFound:
            raise commands.BadArgument('User not found.') from None
        except discord.HTTPException:
            raise commands.BadArgument('An error occurred while fetching the user.') from None


class FetchedChannel(commands.Converter):
    async def convert(self, ctx, argument):
        if not argument.isdigit():
            raise commands.BadArgument('Not a valid channel ID.')
        try:
            return await ctx.bot.fetch_channel(argument)
        except discord.NotFound:
            raise commands.BadArgument('Channel not found.') from None
        except discord.HTTPException:
            raise commands.BadArgument('An error occurred while fetching the channel.') from None


class FetchedGuild(commands.Converter):
    async def convert(self, ctx, argument):
        if not argument.isdigit():
            raise commands.BadArgument('Not a valid guild ID.')
        try:
            return await ctx.bot.fetch_guild(argument)
        except discord.NotFound:
            raise commands.BadArgument('Guild not found.') from None
        except discord.HTTPException:
            raise commands.BadArgument('An error occurred while fetching the guild.') from None
