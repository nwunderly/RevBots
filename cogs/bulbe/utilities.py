
import sys
import psutil
import datetime
from typing import Union

import discord
from discord.ext import commands

from utils.converters import FetchedUser
from utils.utility import status


class PersistManager:
    """Conveniently handles guilds' rolePersist data."""
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        self.table = cog.bot.table

    async def get(self, member):
        try:
            data = self.table.get([member.guild.id, 'rolePersist'])
            roles = data.pop(str(member.id))
            self.table.put(data, [member.guild.id, 'rolePersist'])
            return roles
        except KeyError:
            pass

    async def put(self, member, role_ids):
        try:
            data = self.table.get([member.guild.id, 'rolePersist'])
        except KeyError:
            data = {}
        data[str(member.id)] = role_ids
        self.table.put(data, [member.guild.id, 'rolePersist'])


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.persist = PersistManager(self)

    async def get_autorole_persist_configs(self, guild):
        try:
            config = self.bot.config.get_config(guild)
            utilities = config['utilities']
            return utilities.get('autorole'), utilities.get('persist')
        except KeyError:
            pass

    async def get_persist_config(self, guild):
        try:
            config = self.bot.config.get_config(guild)
            utilities = config['utilities']
            return utilities.get('persist')
        except KeyError:
            pass

    @staticmethod
    async def validate_roles(member, role_ids):
        roles = [member.guild.get_role(r) for r in role_ids]
        roles = [r for r in roles if r is not None]
        roles = [r for r in roles if r not in member.roles]
        roles = [r for r in roles if r.position < member.guild.me.top_role.position]
        return roles

    async def assign_autoroles(self, member, autorole_config):
        roles = await self.validate_roles(member, autorole_config)
        if roles:
            await member.add_roles(*roles, reason="Autorole")

    async def restore_member(self, member, persist_config):
        roles = await self.persist.get(member)

        if not roles:
            return

        roles = [r for r in roles if r in persist_config]
        roles = await self.validate_roles(member, roles)

        if roles:
            await member.add_roles(*roles, reason="Role persist")
            self.bot.dispatch('member_restore', member, roles)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        autorole, persist = await self.get_autorole_persist_configs(member.guild)

        if autorole:
            await self.assign_autoroles(member, autorole)

        if persist:
            await self.restore_member(member, persist)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        persist = await self.get_persist_config(member.guild)

        if not persist:
            return

        roles = [r.id for r in member.roles]
        roles = [r for r in roles if r in persist]

        await self.persist.put(member, roles)

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

        if isinstance(user, discord.Member):
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
        embed.add_field(name="Version", value=self.bot.properties.version)
        embed.add_field(name="Library", value='discord.py')
        embed.add_field(name="OS", value={'linux': 'Ubuntu', 'win32': 'Windows'}[sys.platform])

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
        memory = int(psutil.Process().memory_info().rss//10**6)
        embed.add_field(name="Memory", value=f"{memory} MB")
        embed.add_field(name="Servers", value=len(self.bot.guilds))
        embed.add_field(name="Users", value=len(self.bot.users))

        embed.add_field(name="Source", value='[github](https://github.com/nwunderly/RevBots)')
        embed.add_field(name="Add me!", value='[invite](https://discordapp.com/oauth2/authorize?client_id=548178287013396532&scope=bot&permissions=2134207679)')

        embed.set_footer(text=f'bot by {self.bot._nwunder}', icon_url=self.bot._nwunder.avatar_url)
        embed.timestamp = self.bot.user.created_at
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Utilities(bot))
