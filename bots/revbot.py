
import discord
from discord.ext import commands, tasks

import signal
import asyncio
import datetime
import yaml
import os

# custom imports
from utils import utility
from utils.utility import setup_logger


class RevBot(commands.Bot):
    """

    """
    def __init__(self, name, command_prefix=None, logger=None, **kwargs):
        self._default_prefix = '__'
        command_prefix = command_prefix if command_prefix else self._default_prefix
        super().__init__(command_prefix, **kwargs)
        self.__future = None
        self._revbot_version = '2.0.1'
        self._name = name
        self.logger = logger if logger else setup_logger(name)
        self.started_at = datetime.datetime.now()
        self.logger.debug("RevBot initialization complete.")

    async def try_run(self, coro):
        try:
            return await coro
        except:
            self.logger.error(f"Encountered error in try_run:", exc_info=True)
            return

    async def on_ready(self):
        """
        Override this to override discord.Client on_ready.
        """
        self.logger.info('Logged in as {0.user}.'.format(self))

    async def ping_response(self, channel):
        await channel.send(embed=discord.Embed(title=f"{self._name} ({datetime.datetime.now() - self.started_at})",
                                               description=f"Prefix: `{self.command_prefix}`"))

    async def on_message(self, message):
        if message.author.bot:
            return
        if (await self.is_owner(message.author)) and message.content in [f'<@!{self.user.id}>', f'<@{self.user.id}>']:
            await self.ping_response(message.channel)
        await self.process_commands(message)

    # @tasks.loop(seconds=1)
    # async def watchdog(self):
    #     systemd.daemon.notify("WATCHDOG=1")

    # @staticmethod
    # def sd_notify(arg):
    #     systemd.daemon.notify(arg)

    async def setup(self):
        """
        Called when bot is started, before login.
        Use this for any async tasks to be performed before the bot starts.
        (THE BOT WILL NOT BE LOGGED IN WHEN THIS IS CALLED)
        """
        pass

    async def cleanup(self):
        """
        Called when bot is closed, before logging out.
        Use this for any async tasks to be performed before the bot exits.
        """

    async def read_properties(self):
        try:
            if (filename := f"{self._name}.yaml") in os.listdir(f"{utility.HOME_DIR}/configs"):
                with open(f"{utility.HOME_DIR}/configs/" + filename) as f:
                    properties = yaml.load(f, yaml.Loader)
            else:
                with open(f"{utility.HOME_DIR}/configs/default.yaml") as f:
                    properties = yaml.load(f, yaml.Loader)
            self.properties = self.Properties(properties)
            return True
        except yaml.YAMLError:
            return False

    def run(self, *args, **kwargs):
        self.logger.info("Run method called.")
        super().run(*args, **kwargs)

    async def start(self, *args, **kwargs):
        self.logger.info("Start method called.")
        # self.watchdog.start()
        # self.logger.info("Watchdog loop started. Setting up.")
        await self.setup()
        # self.sd_notify("WATCHDOG=1")
        self.logger.info("Calling super().start method.")
        await super().start(*args, **kwargs)

    async def close(self):
        self.logger.debug("RevBot: Received command to shut down. Beginning safe shutdown sequence.")
        await self.cleanup()
        self.logger.info("Closing connection to discord.")
        await super().close()

    class Properties:
        def __init__(self, properties):
            self.properties_dict = properties
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
