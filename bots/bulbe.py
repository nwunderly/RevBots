# version 2.0

import discord
from discord.ext import tasks, commands

import yaml
import os
import random

# custom imports
from bots.revbot import RevBot
from utils.sheets import SheetsClient


def prefix(bot, message, only_guild_prefix=False):
    default = bot._properties.prefix if bot._properties else bot._default_prefix
    mention = bot.user.mention + " "
    if not message.guild:
        return commands.when_mentioned(bot, message) + default
    if message.guild.id not in bot._config.keys():
        guild_prefix = default
    else:
        config = bot._config[message.guild.id]
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
    def __init__(self, name, logger=None, use_socket=True, command_prefix=prefix, **kwargs):
        super().__init__(name, logger=logger, use_socket=use_socket, command_prefix=command_prefix, case_insensitive=True,
                         description='Best Bot <3', **kwargs)
        self._nwunder = None
        self._properties = None
        self._config = {}
        self._user_blacklist = []
        self._guild_blacklist = []
        self._locked = False
        self.sheets = None
        # self.add_check(checks.global_checks) todo
        self.logger.info(f'Initialization complete. [{name}]')

    async def on_ready(self):
        self.logger.info('Logged in as {0.user}.'.format(self))
        self._nwunder = await self.fetch_user(204414611578028034)
        if not self.command_prefix:
            self.command_prefix = f"++"
        if self._properties:
            self.logger.info("Converting properties.")
            await self._properties.convert(self)
        else:
            self.logger.error("on_ready called but Properties object has not been defined.")
        self.update_presence.start()
        self.logger.info("Bot is ready.")
        # await self.close() # todo

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

    async def process_direct_messages(self, message):
        if message.guild:
            return
        attachments = f'             \n'.join([str(a.url) for a in message.attachments]) if message.attachments else None
        self.logger.info(f"Received direct message from {message.author} ({message.author.id}): \n"
                         f"{message.content}\n"
                         f"Attachments: {attachments}")
        # channel = self.get_channel(self._properties.logging_channel)
        channel = self._properties.logging_channel
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
        prefix = self.command_prefix(self, message, only_guild_prefix=True)
        e = discord.Embed(title=f"Bulbe v{self._properties.version}",
                          color=self._properties.embed_color,
                          description=f"Prefix: `{prefix}`")
        return e

    @tasks.loop(hours=1)
    async def update_presence(self):
        activity = None
        name = random.choice(self._properties.activities)
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

    async def read_properties(self):
        try:
            if (filename := f"{self._name}.yaml") in os.listdir("configs"):
                with open("configs/" + filename) as f:
                    properties = yaml.load(f, yaml.Loader)
            else:
                with open("configs/default.yaml") as f:
                    properties = yaml.load(f, yaml.Loader)
            self._properties = self.Properties(properties)
            return True
        except yaml.YAMLError:
            return False

    def blacklisted(self, *ids):
        for i in ids:
            if i in self._user_blacklist or i in self._guild_blacklist:
                return True
        return False

    def read_blacklists(self):
        try:
            blacklists = self.sheets.read_blacklists(self._name)
            self._user_blacklist, self._guild_blacklist = blacklists
            return True
        except Exception as e:
            print(str(e))
            self._user_blacklist, self._guild_blacklist = [], []
            return False

    def write_blacklists(self):
        users = []
        guilds = []
        for user_id in self._user_blacklist:
            users.append([user_id, str(self.get_user(user_id))])
        for guild_id in self._guild_blacklist:
            guilds.append([guild_id, str(self.get_guild(guild_id))])
        data = users, guilds
        try:
            self.sheets.write_blacklists(self._name, data)
            return True
        except Exception:
            return False

    class Properties:
        def __init__(self, properties):
            self._properties_dict = properties
            for key in properties.keys():
                value = properties[key]
                key = key.replace(" ", "_")
                setattr(self, key, value)

        async def convert(self, bot):
            converters = {
                "embed_color": lambda c: discord.Color(int(c, 16)),
                "socket": bool,  # deprecated
                "logging_channel": bot.get_channel
            }
            for key in self.__dict__:
                if key in converters.keys():
                    attr = getattr(self, key)
                    value = converters[key](attr)
                    setattr(self, key, value)

    async def setup(self):
        self.logger.info('Loading YAML data.')
        p = await self.read_properties()
        if not p:
            self.logger.error('Error reading properties file. Shutting down.')
            await self.close()
        self.sheets = SheetsClient(self._name)
        self.logger.info('Loading cogs.')
        self.logger.info('YAML data loaded.')
        for cog in self._properties.cogs:
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

    async def close(self):
        self.logger.debug("Bulbe: Received command to shut down. Beginning safe shutdown sequence.")
        # self.logger.info("Locking bot.")
        # await self.lock()
        self.logger.info("Dumping data.")
        self.write_blacklists()
        # write_guild_data()
        self.logger.info("Closing connection to socket.")
        # close() unloads cogs
        await super().close()

