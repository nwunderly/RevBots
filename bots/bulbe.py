
import discord
from discord.ext import tasks, commands

import yaml
import os
import sys
import copy
import random
import collections
import aiohttp

# custom imports
from bots.revbot import RevBot
from utils.db import Table
from utils import checks, utility


def prefix(bot, message, only_guild_prefix=False):
    default = bot.properties.prefix if bot.properties else bot.default_prefix
    if not message.guild:
        return commands.when_mentioned(bot, message) + [default]
    if bot.config:
        config = bot.config.get_config(message.guild)
        p = config['prefix']
    else:
        p = None
    p = p if p else default
    if only_guild_prefix:
        return p
    else:
        return commands.when_mentioned(bot, message) + [p]


class Bulbe(RevBot):
    def __init__(self, name, logger, **kwargs):
        super().__init__(name, logger=logger, command_prefix=prefix, case_insensitive=True,
                         description='Best Bot <3', **kwargs)
        self._init_args = [name, logger]
        self._init_kwargs = kwargs
        self._nwunder = None
        self.config = None
        self._user_blacklist = []
        self._guild_blacklist = []
        self._locked = False
        self.table = None
        self.help_command = commands.MinimalHelpCommand()
        self.add_check(checks.global_checks)
        self.logger.info(f'Initialization complete. [{name}]')

    async def on_ready(self):
        self.logger.info('Logged in as {0.user}.'.format(self))
        self._nwunder = await self.fetch_user(204414611578028034)
        if self.properties:
            self.logger.info("Converting properties.")
            await self.properties.convert(self)
        else:
            self.logger.error("on_ready called but Properties object has not been defined.")
        self.update_presence.start()
        self.logger.info(f"Bot is ready, version {self.properties.version}!")

    async def on_message(self, message):
        if message.author.bot:
            return
        if message.guild:
            await self.process_mention(message)
            await self.process_commands(message)
        else:
            await self.process_direct_messages(message)

    async def on_command_error(self, ctx, exception):
        await super().on_command_error(ctx, exception)
        if isinstance(exception, commands.CommandInvokeError):
            self.logger.error(f"Error invoking command '{ctx.command.qualified_name}' / "
                              f"author {ctx.author.id}, guild {ctx.guild.id if ctx.guild else None}, channel {ctx.channel.id}, message {ctx.message.id}"
                              f"{exception.__class__.__name__}: {exception}")

    async def on_command_completion(self, ctx):
        self.logger.info(f"Command '{ctx.command.qualified_name}' invoked / "
                         f"author {ctx.author.id}, guild {ctx.guild.id if ctx.guild else None}, channel {ctx.channel.id}, message {ctx.message.id}")
        # await self.update_stats(ctx)

    async def lock(self):
        self._locked = True
        self.update_presence.stop()
        await self.change_presence(activity=discord.Game(name="LOCKED"), status=discord.Status.do_not_disturb)
        self.logger.info('Bot has been locked.')

    async def unlock(self):
        self._locked = False
        self.update_presence.start()
        self.logger.info('Bot has been unlocked.')

    def is_locked(self):
        return self._locked

    async def process_direct_messages(self, message):
        if message.guild:
            return
        attachments = f'             \n'.join([str(a.url) for a in message.attachments]) if message.attachments else None
        self.logger.info(f"Received direct message from {message.author} ({message.author.id}): \n"
                         f"{message.content}\n"
                         f"Attachments: {attachments}")
        channel = self.properties.logging_channel
        if len(message.content) > 1500:
            content = message.clean_content[:1500] + f".... {len(message.clean_content)}"
        else:
            content = message.clean_content
        forward_message = f"Received direct message from {message.author} ({message.author.id}):\n{content}"
        forward_message += ("\nAttachments:\n" + '\n'.join([str(a.url) for a in message.attachments])) if message.attachments else ""
        await channel.send(forward_message)

    async def process_mention(self, message):
        if message.content in [self.user.mention, '<@!%s>' % self.user.id]:
            await message.channel.send(embed=self.get_embed(message))

    def get_embed(self, message=None):
        p = self.command_prefix(self, message, only_guild_prefix=True)
        e = discord.Embed(title=f"Bulbe v{self.properties.version}",
                          color=self.properties.embed_color,
                          description=f"Prefix: `{p}`")
        return e

    @tasks.loop(minutes=20)
    async def update_presence(self):
        activity = None
        name = random.choice(self.properties.activities)
        if name.lower().startswith("playing "):
            activity = discord.Game(name.replace("playing ", ""))
        elif name.lower().startswith("watching "):
            activity = discord.Activity(type=discord.ActivityType.watching,
                                        name=name.replace("watching", ""))
        elif name.lower().startswith("listening to "):
            activity = discord.Activity(type=discord.ActivityType.listening,
                                        name=name.replace("listening to ", ""))
        if activity:
            await self.change_presence(activity=activity)

    def blacklisted(self, *ids):
        for i in ids:
            if i in self._user_blacklist or i in self._guild_blacklist:
                return True
        return False

    def read_blacklists(self):
        try:
            data = self.table.get([0, 'blacklists'])
            # primary key 0 means general bot data
            users, guilds = data['users'], data['guilds']
            self._user_blacklist = [user[0] for user in users]
            self._guild_blacklist = [guild[0] for guild in guilds]
            return True
        except Exception as e:
            self.logger.error("Error in read_blacklists.", exc_info=True)
            self._user_blacklist, self._guild_blacklist = [], []
            return False

    def write_blacklists(self):
        users = []
        guilds = []
        data = dict()
        for user_id in self._user_blacklist:
            users.append([user_id, str(self.get_user(user_id))])
        for guild_id in self._guild_blacklist:
            guilds.append([guild_id, str(self.get_guild(guild_id))])
        data['users'], data['guilds'] = users, guilds
        try:
            self.table.put(data, [0, 'blacklists'])
            return True
        except Exception:
            return False

    async def setup(self):
        self.logger.info('Loading YAML data.')
        p = await self.read_properties()
        if not p:
            self.logger.error('Error reading properties file. Shutting down.')
            await self.close(-1)
        self.logger.info("Setting up DynamoDB table.")
        try:
            self.table = Table('Bulbe')
        except:
            self.logger.error("Error setting up table. Shutting down.")
            await self.close(-1)
        self.logger.info('Loading cogs.')
        for cog in self.properties.cogs:
            try:
                self.load_extension(cog)
                self.logger.info(f"-> Loaded {cog}.")
            except Exception as e:
                self.logger.error(f"-> Failed to load extension {cog}.", exc_info=True)
        b = self.read_blacklists()
        if not b:
            self.logger.error("Error reading blacklists. Continuing without blacklists")

    async def cleanup(self):
        self.logger.info("Dumping data.")
        self.write_blacklists()

