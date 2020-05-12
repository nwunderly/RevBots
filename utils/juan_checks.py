import discord
from discord.ext import commands

"""
RECOMMENDED WAY TO IMPORT THIS FILE:
from utils import juan_checks as checks

    - unrestricted: this and owner return True for all checks
    - systemAdmin: exclusively bot management related stuff
    - guildAdmin: moderation stuff and server management stuff
    - guildMod: moderation related stuff
    - developer: general commands on the bot
    
"""


async def global_check(ctx):
    # protection for discord.py guild
    if await ctx.bot.is_owner(ctx.author):
        return True
    return ctx.guild.id in [537043976562409482, 576168356823040010]
#                                eat pant              juan


def bot_perms(permission):
    async def pred(ctx):
        return await juan_perm_check(ctx, permission)
    return commands.check(pred)


def is_admin():
    async def pred(ctx):
        return await juan_perm_check(ctx, 'guildAdmin')
    return commands.check(pred)


def is_mod():
    async def pred(ctx):
        return await juan_perm_check(ctx, 'guildMod')
    return commands.check(pred)


def is_developer():
    async def pred(ctx):
        return await juan_perm_check(ctx, 'guildMod')
    return commands.check(pred)


# ----------------------------------------------------------------------------------------------------------------------------------------------------


# Don't use this one
async def juan_perm_check(ctx, permission):
    """
    Checks purely the requested permission.
    """
    if await ctx.bot.is_owner(ctx.author):
        # if it's me
        return True

    # function to make it easier
    def check(field):
        if isinstance(field, list):
            return permission in field or 'unrestricted' in field
        elif isinstance(field, str):
            return permission == field or 'unrestricted' == field
        return False

    # checks perms associated with user id
    perms = ctx.bot.properties.perms
    if ctx.author.id in perms.keys() and check(ctx.bot.properties.perms[ctx.author.id]):
        return True

    # checks perms associated with user's roles
    for role in ctx.author.roles:
        if role.id in perms.keys() and check(perms[role.id]):
            return True

    # if it's here, access will be denied.
    return False


