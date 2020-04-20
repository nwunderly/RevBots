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


class CachedGuild(commands.Converter):
    async def convert(self, ctx, argument):
        if not argument.isdigit():
            raise commands.BadArgument('Not a valid guild ID.')
        try:
            return ctx.bot.get_guild(argument)
        except discord.NotFound:
            raise commands.BadArgument('Guild not found.') from None
        except discord.HTTPException:
            raise commands.BadArgument('An error occurred while fetching the guild.') from None


class GlobalChannel(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            return await commands.TextChannelConverter().convert(ctx, argument)
        except commands.BadArgument:
            # Not found... so fall back to ID + global lookup
            try:
                channel_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(f'Could not find a channel by ID {argument!r}.')
            else:
                channel = ctx.bot.get_channel(channel_id)
                if channel is None:
                    raise commands.BadArgument(f'Could not find a channel by ID {argument!r}.')
                return channel


class OptionFlag(commands.Converter):
    async def convert(self, ctx, argument):
        if not argument.startswith('--'):
            raise commands.BadArgument()
        return argument[2:]


class Language(commands.Converter):
    async def convert(self, ctx, argument):
        argument = argument.lower()

        def update_langs():
            langs = ctx.cog.translator.get_languages(target_language='en')
            for lang in langs:
                ctx.cog.lang_cache[lang['name'].lower()] = lang['language']

        def get_lang():
            if argument in ctx.cog.lang_cache.keys():
                return ctx.cog.lang_cache[argument]
            elif argument in ctx.cog.lang_cache.values():
                return argument

        result = get_lang()
        if result:
            return result

        update_langs()
        result = get_lang()
        if result:
            return result

        raise commands.BadArgument("Could not convert to a supported language.")


class Command(commands.Converter):
    async def convert(self, ctx, argument):
        command = ctx.bot.get_command(argument)
        if command:
            return command
        else:
            raise commands.BadArgument("A command with this name could not be found.")


class Module(commands.Converter):
    async def convert(self, ctx, argument):
        cog = ctx.bot.get_cog(argument)
        if cog:
            return cog
        else:
            raise commands.BadArgument("A module with this name could not be found.")
