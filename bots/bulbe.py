
import discord
from discord.ext import tasks, commands

import yaml
import os
import sys
import random
import collections

# custom imports
from bots.revbot import RevBot
from utils.db import Table
from utils import utility


def prefix(bot, message, only_guild_prefix=False):
    default = bot.properties.prefix if bot.properties else bot.default_prefix
    if not message.guild:
        return commands.when_mentioned(bot, message) + [default]
    if message.guild.id not in bot.config.keys():
        guild_prefix = default
    else:
        config = bot.config[message.guild.id]
        if 'prefix' in config.keys():
            p = config.get('prefix')
            guild_prefix = p if p else default
        else:
            guild_prefix = default
    if only_guild_prefix:
        return guild_prefix
    else:
        return commands.when_mentioned(bot, message) + [guild_prefix]


class Bulbe(RevBot):
    def __init__(self, name, logger=None, command_prefix=prefix, **kwargs):
        super().__init__(name, logger=logger, command_prefix=command_prefix, case_insensitive=True,
                         description='Best Bot <3', **kwargs)
        self._nwunder = None
        self.config = collections.defaultdict(default_factory=lambda: {})
        self._user_blacklist = []
        self._guild_blacklist = []
        self._locked = False
        self.properties = None
        self.table = None
        # self.add_check(checks.global_checks) todo
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
        self.logger.info("Bot is ready.")

    # async def on_error(self, event_method, *args, **kwargs):
    #     # self.logger.error(f"Error in event {str(event_method)}", exc_info=True, stack_info=True)
    #     self.logger.error(f'Ignoring exception in {event_method}', exc_info=True)
    #     self.logger.error(f"(on_error) Traceback.format_exc():\n{traceback.format_exc()}")
    #
    # async def on_command_error(self, context, exception):
    #     self.logger.error(f'Ignoring exception in command {context.command}', exc_info=True)
    #     self.logger.error(f"(on_command_error) Traceback.format_exc():\n{traceback.format_exc()}")

    async def on_message(self, message):
        if message.author.bot:
            return
        if message.guild:
            await self.process_mention(message)
            await self.process_commands(message)
        else:
            await self.process_direct_messages(message)

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
        # channel = self.get_channel(self._properties.logging_channel)
        channel = self.properties.logging_channel
        if len(message.content) > 1500:
            content = message.clean_content[:1500] + f".... {len(message.clean_content)}"
        else:
            content = message.clean_content
        forward_message = f"Received direct message from {message.author} ({message.author.id}):\n{content}"
        forward_message += ("\nAttachments:" + '\n'.join([str(a.url) for a in message.attachments])) if message.attachments else ""
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

    @tasks.loop(hours=1)
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
            print(str(e))
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
        self.logger.info("Setup method called.")
        self.logger.info('Loading YAML data.')
        p = await self.read_properties()
        if not p:
            self.logger.error('Error reading properties file. Shutting down.')
            await self.close()
        self.logger.info('YAML data loaded.')
        self.logger.info("Setting up DynamoDB table.")
        self.table = Table('Bulbe')
        self.logger.info('Loading cogs.')
        for cog in self.properties.cogs:
            self.logger.info(f'Loading {cog}.')
            try:
                self.load_extension(cog)
                self.logger.info(f"Loaded extension {cog}.")
            except Exception as e:
                self.logger.error(f"Failed to load extension {cog}.", exc_info=True)
        b = self.read_blacklists()
        if not b:
            self.logger.error("Error reading blacklist file. Bot will not have blacklists.")
        self.logger.info('Setup complete.')

    async def cleanup(self):
        self.logger.info("Dumping data.")
        self.write_blacklists()

