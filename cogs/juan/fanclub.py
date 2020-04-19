
import discord
from discord.ext import commands
from discord.ext import tasks

import datetime
import asyncio
import decimal
import yaml
import re
import copy
import collections

from utils import juan_checks as checks
from utils import db
from utils import converters


VISITOR_ROLE = 582405430274293770
DEVELOPER_ROLE = 582399407698477057
MANAGE_GUILD = 582741228274319380
DEFAULT_BOT_COLOR = 590977254008553494
BOTS_ROLE = 576258076957605889
DEV_CHANNELS_CATEGORY = 577706266768703488
MOD_BOTS_ROLE = 590977954474098700
BOT_LORDS_ROLE = 664328292522000424


pattern = re.compile(r"^= ([\w| ]+) =$")


def sort_roles(roles):
    role_list = copy.copy(roles)
    role_list.reverse()
    _sorted = collections.defaultdict(list)
    category = "top"
    for role in role_list:
        match = pattern.fullmatch(role.name)
        if match:
            category = match.group(1)
        else:
            _sorted[category].append(role)
    return _sorted


def get_category_list(roles):
    role_list = copy.copy(roles)
    role_list.reverse()
    categories = list()
    for role in roles:
        match = pattern.fullmatch(role.name)
        if match:
            categories.append(role)
    return categories


class DevData:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        self.table = cog.table

    def get(self, user_id, key=None):
        try:
            if key:
                return self.table.get([user_id, 'devData'])[key]
            else:
                return self.table.get([user_id, 'devData'])
        except KeyError:
            return None

    def put(self, new_data, user_id):
        try:
            data = self.table.get([user_id, 'devData'])
        except KeyError:
            data = {}
        data.update(new_data)
        self.table.put(data, [user_id, 'devData'])

    def get_all(self):
        data = self.table.read('devData')
        for item in data:
            item.pop('dataType')
            item['user'] = item.pop('snowflake')
        return data

    def get_bot(self, bot_id):
        data = self.get_all()
        for user_data in data:
            for bot_data in user_data['bots']:
                if bot_data['id'] == bot_id:
                    bot_data['owner'] = user_data['user']
                    return bot_data
        return None

    def whose_bot(self, bot_id):
        data = self.get_all()
        for user_data in data:
            for bot_data in user_data['bots']:
                if bot_data['id'] == bot_id:
                    return user_data['user']
        return None

    def whose_channel(self, channel_id):
        data = self.get_all()
        for user_data in data:
            if 'devChannel' not in user_data.keys():
                continue
            if user_data['devChannel'] == channel_id:
                return user_data['user']
        return None

    def whose_role(self, role_id):
        data = self.get_all()
        for user_data in data:
            if 'botRole' not in user_data.keys():
                continue
            if user_data['botRole'] == role_id:
                return user_data['user']
        return None


class FanClub(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.table = self.bot.table
        self.dev_data = DevData(self)

    @commands.Cog.listener()
    async def on_ready(self):
        self.cleanup_roles.start()

    @tasks.loop(minutes=30)
    async def cleanup_roles(self):
        guild = self.bot.get_guild(self.bot.properties.guild)
        category_roles = get_category_list(guild.roles)
        bot_roles = [guild.get_role(role) for role in [BOTS_ROLE, BOT_LORDS_ROLE, MOD_BOTS_ROLE]]
        dev_bot_roles = sort_roles(guild.roles).get('Special Bot Roles')
        for member in guild.members:
            for role in category_roles:
                if role in member.roles:
                    await member.remove_roles(*category_roles, reason="Role cleanup")
                    break
            if not member.bot:
                for role in bot_roles:
                    if role in member.roles:
                        await member.remove_roles(*bot_roles, reason="Role cleanup")
                        break
                # for role in dev_bot_roles:
                #     if role in member.roles:
                #         await member.remove_roles(*dev_bot_roles, reason="Role cleanup")
                #         break

    def get_bots(self, user):
        if isinstance(user, int) or isinstance(user, decimal.Decimal):
            return self.dev_data.get(user, 'bots')
        return self.dev_data.get(user.id, 'bots')

    def get_dev_channel(self, user):
        if isinstance(user, int) or isinstance(user, decimal.Decimal):
            return self.dev_data.get(user, 'devChannel')
        return self.dev_data.get(user.id, 'devChannel')

    def get_bot_role(self, user):
        if isinstance(user, int) or isinstance(user, decimal.Decimal):
            return self.dev_data.get(user, 'botRole')
        return self.dev_data.get(user.id, 'botRole')

    def update_dev_data(self, new_data, user_id, key):
        data = {key: new_data}
        self.dev_data.put(data, user_id)

    def register_bot(self, user, bot_data):
        user_id = user if isinstance(user, int) or isinstance(user, decimal.Decimal) else user.id
        bot_data['timestamp'] = str(datetime.datetime.now())
        bots = self.get_bots(user_id)
        if bots:
            for bot in bots:
                if bot['id'] == bot_data['id']:
                    bots.remove(bot)
        else:
            bots = []
        bots.append(bot_data)
        self.update_dev_data(bots, user_id, 'bots')

    @staticmethod
    async def added_by(member):
        async for entry in member.guild.audit_logs(limit=10, action=discord.AuditLogAction.bot_add):
            if entry.target == member:
                return entry.user
        return None

    async def handle_unregistered_bot(self, member):
        added_by = await self.added_by(member)
        added_by_id = added_by.id if added_by else None
        await member.kick(reason=f"Unregistered bot, added by {added_by} ({added_by_id})")
        logs = self.bot.get_channel(self.bot.properties.channels['logs'])
        await logs.send(f"{datetime.datetime.now()}: {member} has been kicked: unregistered bot, added by {added_by} ({added_by_id}).")
        general = self.bot.get_channel(self.bot.properties.channels['general'])
        await general.send(f"{member} has been kicked." + (f" {added_by.mention}, p" if added_by else " P") +
                           "lease register your bot with me before adding it to this server.")

    async def handle_registered_bot(self, member, bot_data):
        added_by = await self.added_by(member)
        roles = []

        timestamp = bot_data['timestamp'] if 'timestamp' in bot_data.keys() else "No timestamp"
        owner_id = bot_data['owner'] if 'owner' in bot_data.keys() else None

        bot_role_id = self.get_bot_role(owner_id)

        try:
            owner = await self.bot.fetch_user(owner_id)
        except discord.NotFound:
            owner = None
        added_by_id = added_by.id if added_by else None

        self.bot.dispatch('bot_add', member, added_by, owner)

        if bot_role_id:
            roles.append(member.guild.get_role(bot_role_id))
        else:
            roles.append(member.guild.get_role(DEFAULT_BOT_COLOR))

        roles.append(member.guild.get_role(BOTS_ROLE))

        if roles:
            await member.add_roles(*roles, reason=f"Bot added by {added_by} ({added_by_id}), registered to {owner} ({owner_id}) [{timestamp}]")

        logs = self.bot.get_channel(self.bot.properties.channels['logs'])
        await logs.send(f"{datetime.datetime.now()}: {member} added by {added_by} ({added_by_id}), registered to {owner} ({owner_id}) [{timestamp}]")

        general = self.bot.get_channel(self.bot.properties.channels['general'])
        await general.send(f"{added_by.mention if added_by else None} has added bot {member.mention} to the server!")

        if not owner or owner not in member.guild.members:
            return
        owner = member.guild.get_member(owner.id)

        bots = self.get_bots(owner)
        if len(bots) == 1:
            role = member.guild.get_role(DEVELOPER_ROLE)
            if role not in member.roles:
                await owner.add_roles(role, reason="First bot! 🎉")
            await general.send(f"Congrats {owner.mention} on adding your first bot! 🎉")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != self.bot.properties.guild:
            return
        if not member.bot:
            general = self.bot.get_channel(self.bot.properties.channels['general'])
            visitor_role = member.guild.get_role(VISITOR_ROLE)
            await general.send(f"Welcome {member.mention}!")
            await member.add_roles(visitor_role, reason="Autorole")
            return
        bot_data = self.dev_data.get_bot(member.id)
        await asyncio.sleep(2)
        if bot_data:
            await self.handle_registered_bot(member, bot_data)
        else:
            await self.handle_unregistered_bot(member)

    @commands.command()
    async def bots(self, ctx, who: discord.Member = None):
        who = who if who else ctx.author
        bots = self.get_bots(who.id)
        for bot_info in bots:
            for key, value in bot_info.items():
                if isinstance(value, decimal.Decimal):
                    bot_info[key] = str(self.bot.get_user(int(value)))
        formatted = yaml.dump(bots)
        await ctx.send(f"```{formatted}```")

    @commands.command()
    async def bot(self, ctx, who: discord.Member):
        bot_info = self.dev_data.get_bot(who)
        for key, value in bot_info.items():
            if isinstance(value, decimal.Decimal):
                bot_info[key] = str(self.bot.get_user(int(value)))
        formatted = yaml.dump(bot_info)
        await ctx.send(f"```{formatted}```")

    @commands.command()
    async def whosebot(self, ctx, bot: discord.Member):
        owner = self.dev_data.whose_bot(bot.id)
        await ctx.send(f"This bot is registered to {owner}.")

    @commands.command()
    async def whosechannel(self, ctx, channel: discord.TextChannel):
        owner = self.dev_data.whose_channel(channel.id)
        await ctx.send(f"This channel is registered to {owner}.")

    @commands.command()
    async def whoserole(self, ctx, role: discord.Role):
        owner = self.dev_data.whose_role(role.id)
        await ctx.send(f"This role is registered to {owner}.")

    @commands.command()
    @checks.is_admin()
    async def forceregister(self, ctx, owner_id: int, bot_id: int, prefix):
        try:
            data = {
                'id': bot_id,
                'prefix': prefix
            }
            owner = await self.bot.fetch_user(owner_id)
            self.register_bot(owner, data)
            await ctx.send(f"Registered {bot_id} to {owner_id}.")
        except Exception as e:
            await ctx.send(str(e))

    @commands.command()
    async def addbot(self, ctx, bot_id: int, prefix):
        url = discord.utils.oauth_url(str(bot_id))

        data = {
            'id': bot_id,
            'prefix': prefix
        }
        self.register_bot(ctx.author, data)

        manage_guild = ctx.guild.get_role(MANAGE_GUILD)
        await ctx.author.add_roles(manage_guild, reason=f"Perms to add bot, client id {bot_id}")

        def check(bot, added_by, owner):
            return ctx.author.id in [added_by.id if added_by else None, owner.id if owner else None]

        await ctx.send("<" + url + ">")

        try:
            await self.bot.wait_for('bot_add', check=check, timeout=600)
        except asyncio.TimeoutError:
            pass

        await ctx.author.remove_roles(manage_guild, reason="Added bot or request timed out")

    @commands.command()
    @checks.is_developer()
    async def register(self, ctx, bot: discord.Member, prefix):
        owner_id = self.dev_data.whose_bot(bot)
        if owner_id:
            try:
                owner = await self.bot.fetch_user(owner_id)
            except discord.NotFound:
                owner = None
            await ctx.send(f"{bot} is already owned by {owner if owner else owner_id}!")
        data = {
            'id': bot.id,
            'prefix': prefix
        }
        self.register_bot(ctx.author, data)
        role = self.get_bot_role(ctx.author)
        if role:
            role = ctx.guild.get_role(role)
            if role:
                try:
                    timestamp = self.dev_data.get_bot(bot.id)['timestamp']
                except TypeError:
                    timestamp = None
                await bot.add_roles(role, reason=f"Registered to {ctx.author} ({ctx.author.id}) [{timestamp}]")
        await ctx.send(f"Registered {bot} to {ctx.author}.")

    @commands.command()
    @checks.is_admin()
    async def unregister(self, ctx, bot_id: int):
        n = 0
        while (bot_data := self.dev_data.get_bot(bot_id)) is not None:
            user_id = bot_data.pop('owner')
            bots = self.dev_data.get(user_id, 'bots')
            for bot in bots:
                if bot['id'] == bot_id:
                    n += 1
                    bots.remove(bot)
                    await ctx.send(f"Removed from bots owned by user {user_id}.")

            self.update_dev_data(bots, user_id, 'bots')
        await ctx.send(f"Done. Bot was registered {n} times.")

    @commands.command()
    @checks.is_developer()
    async def claimchannel(self, ctx, channel: discord.TextChannel):
        if channel.category.id != DEV_CHANNELS_CATEGORY:
            await ctx.send("Channel must be in \"Dev Channels\" category.")
            return
        owner = self.dev_data.whose_channel(channel)
        if owner:
            await ctx.send(f"That channel is owned by {owner}.")
            return
        self.update_dev_data(channel.id, ctx.author.id, 'devChannel')
        await ctx.send("Done!")

    @commands.command()
    @checks.is_developer()
    async def claimrole(self, ctx, role: discord.Role):
        owner = self.dev_data.whose_role(role)
        if owner:
            await ctx.send(f"That role is owned by {owner}.")
            return
        sorted_roles = sort_roles(ctx.guild.roles)
        if role not in sorted_roles['Special Bot Roles']:
            await ctx.send("Role must be in \"Special Bot Roles\" category.")
        self.update_dev_data(role.id, ctx.author.id, 'botRole')
        await ctx.send("Done!")


def setup(bot):
    bot.add_cog(FanClub(bot))
