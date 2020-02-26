import discord
from discord.ext import commands


# todo
#   locked check
#   bot admin check
#   bot operator check
#   make danny checks override correctly
#   user_has_permissions vs bot_has_permissions vs check_permissions
#   uses bot._properties now


async def global_checks(ctx):
    # return await bulbe_perm_check(ctx, "admin")
    if await bulbe_perm_check(ctx, "admin"):
        return True
    if ctx.guild is None:
        return False
    if ctx.bot._locked:
        return False
    if ctx.message.startswith("__"):
        return False
    if ctx.bot.blacklisted([ctx.author.id, ctx.guild.id, ctx.guild.owner.id]):
        try:
            await ctx.send("I won't respond to commands by blacklisted users or in blacklisted guilds!")
        except discord.Forbidden:
            pass
        return False


async def bulbe_perm_check(ctx, permission):
    if await ctx.bot.is_owner(ctx.author):
        return True
    return permission in ctx.bot._properties.bot_admins[ctx.author.id]


def bulbe_perms(permission):
    async def pred(ctx):
        if await bulbe_perm_check(ctx, "admin"):
            return True
        return await bulbe_perm_check(ctx, permission)
    return commands.check(pred)


def bot_admin():
    async def pred(ctx):
        return await bulbe_perm_check(ctx, "admin")
    return commands.check(pred)



# ----------------------------------------------------------------------------------------------------------------------


async def check_permissions(ctx, perms, *, check=all):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    resolved = ctx.channel.permissions_for(ctx.author)
    return check(getattr(resolved, name, None) == value for name, value in perms.items())


def has_permissions(*, check=all, **perms):
    async def pred(ctx):
        return await check_permissions(ctx, perms, check=check)
    return commands.check(pred)


async def check_guild_permissions(ctx, perms, *, check=all):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    if ctx.guild is None:
        return False

    resolved = ctx.author.guild_permissions
    return check(getattr(resolved, name, None) == value for name, value in perms.items())


def has_guild_permissions(*, check=all, **perms):
    async def pred(ctx):
        return await check_guild_permissions(ctx, perms, check=check)
    return commands.check(pred)

# These do not take channel overrides into account


def is_mod():
    async def pred(ctx):
        return await check_guild_permissions(ctx, {'manage_guild': True})
    return commands.check(pred)


def is_admin():
    async def pred(ctx):
        return await check_guild_permissions(ctx, {'administrator': True})
    return commands.check(pred)


def mod_or_permissions(**perms):
    perms['manage_guild'] = True

    async def predicate(ctx):
        return await check_guild_permissions(ctx, perms, check=any)
    return commands.check(predicate)


def admin_or_permissions(**perms):
    perms['administrator'] = True

    async def predicate(ctx):
        return await check_guild_permissions(ctx, perms, check=any)
    return commands.check(predicate)


def is_in_guilds(*guild_ids):
    def predicate(ctx):
        guild = ctx.guild
        if guild is None:
            return False
        return guild.id in guild_ids
    return commands.check(predicate)
