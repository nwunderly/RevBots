
import sys
import psutil
import datetime
from typing import Union

import discord
from discord.ext import commands

from utils.converters import FetchedUser


status = {
    'online': '<:status_online:699642822378258547>',
    'idle': '<:status_idle:699642825087647784>',
    'dnd': '<:status_dnd:699642826585145397>',
    'offline': '<:status_offline:699642828309004420>',
    'streaming': '<:status_streaming:699642830842363984>'
}


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def serverinfo(self, ctx):
        """Some info about this server."""
        embed = self.bot.Embed(description=ctx.guild.id)
        embed.set_author(name=ctx.guild.name)
        embed.set_thumbnail(url=ctx.guild.icon_url)

        def bot(_bool):
            return list(filter(lambda m: m.bot == _bool, ctx.guild.members))

        embed.add_field(name='Owner', value=f'{ctx.guild.owner} ({ctx.guild.owner.mention})', inline=False)
        embed.add_field(name='Created', value=f'{ctx.guild.created_at:%m/%d/%Y}')
        embed.add_field(name='Members', value=f"{len(ctx.guild.members)}")
        embed.add_field(name='Humans', value=f"{len(bot(False))}")
        embed.add_field(name='Bots', value=f"{len(bot(True))}")
        embed.add_field(name='Roles', value=len(ctx.guild.roles))
        embed.add_field(name='Channels', value=len(ctx.guild.channels))
        embed.add_field(name='Text Channels', value=len(ctx.guild.text_channels))
        embed.add_field(name='Voice Channels', value=len(ctx.guild.voice_channels))
        embed.add_field(name='Categories', value=len(ctx.guild.categories))

        await ctx.send(embed=embed)

    @commands.command()
    async def userinfo(self, ctx, user: Union[discord.Member, discord.User, FetchedUser] = None):
        """Info about a user."""
        user = user if user else ctx.author
        embed = self.bot.Embed(description=user.id, color=user.color if user.color.value != 0 else None)
        embed.set_author(name=str(user))
        embed.set_thumbnail(url=user.avatar_url)

        embed.add_field(name='Status', value=status[str(user.status)], inline=False)
        embed.add_field(name='Shared Servers', value=f'{sum(g.get_member(user.id) is not None for g in self.bot.guilds)}', inline=False)

        if isinstance(user, discord.Member):
            order = sorted(ctx.guild.members, key=lambda m: m.joined_at)
            join_pos = order.index(user) + 1

            embed.add_field(name='Join Position', value=join_pos, inline=False)
            embed.add_field(name='Roles', value=len(user.roles)-1, inline=False)

        embed.add_field(name='Created', value=f'{user.created_at:%m/%d/%Y}', inline=False)

        if isinstance(user, discord.Member):
            embed.add_field(name='Joined', value=f"{getattr(user, 'joined_at', None):%m/%d/%Y}", inline=False)

            important_perms = ['manage_guild', 'manage_roles', 'manage_channels',  'ban_members', 'kick_members', 'manage_messages']
            owner = user.guild.owner == user
            admin = user.guild_permissions.administrator
            permissions = list(perm for perm in important_perms if getattr(user.guild_permissions, perm))
            perms = 'server owner' if owner else ('administrator' if admin else (', '.join(permissions) if permissions else None))

            if perms:
                embed.add_field(name='Permissions', value=perms, inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def botinfo(self, ctx):
        """Some info about me!"""
        embed = self.bot.Embed()
        embed.set_author(name=str(self.bot.user), icon_url=self.bot.user.avatar_url)
        embed.add_field(name="Creator", value=str(self.bot._nwunder))
        embed.add_field(name="Version", value=self.bot.properties.version)
        embed.add_field(name="Library", value='discord.py')

        dt = datetime.datetime.now()-self.bot.started_at
        if dt.days >= 7:
            uptime = f"{(_w := dt.days//7)} week" + ('s' if _w > 1 else '')
        elif dt.days >= 1:
            uptime = f"{(_d := dt.days)} day" + ('s' if _d > 1 else '')
        elif dt.seconds > 3599:
            uptime = f"{(_h := dt.seconds//3600)} hour" + ('s' if _h > 1 else '')
        elif dt.seconds > 59:
            uptime = f"{(_m := dt.seconds//60)} minute" + ('s' if _m > 1 else '')
        else:
            uptime = f"{dt.seconds} seconds"

        embed.add_field(name="Uptime", value=uptime)
        embed.add_field(name="OS", value={'linux': 'Ubuntu', 'win32': 'Windows'}[sys.platform])
        memory = int(psutil.Process().memory_percent()/100*psutil.virtual_memory().available//10**6)
        embed.add_field(name="Memory", value=f"{memory} MB")
        embed.add_field(name="Servers", value=len(self.bot.guilds))
        embed.add_field(name="Users", value=len(self.bot.users))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Utilities(bot))
