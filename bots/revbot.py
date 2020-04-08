
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

VERSION = "1.0.2"


class RevBot(commands.AutoShardedBot):
    """

    """
    def __init__(self, name, command_prefix=None, logger=None, **kwargs):
        self._default_prefix = '__'
        command_prefix = command_prefix if command_prefix else self._default_prefix
        super().__init__(command_prefix, **kwargs)
        self._revbot_version = VERSION
        self._name = name
        self.properties = None
        self._exit_code = 0
        self.logger = logger if logger else setup_logger(name)
        self.started_at = datetime.datetime.now()
        self.logger.debug(f"RevBot initialization complete. [{VERSION}]")

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
        pass

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
        self.logger.debug("Run method called.")
        super().run(*args, **kwargs)

    async def start(self, *args, **kwargs):
        self.logger.debug("Start method called.")
        try:
            self.loop.remove_signal_handler(signal.SIGINT)
            self.loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(self.close()))
        except NotImplementedError:
            pass
        # self.watchdog.start()
        # self.logger.info("Watchdog loop started.")
        self.logger.info("Setting up.")
        await self.setup()
        self.logger.debug("Setup complete.")
        self.logger.debug("Calling super().start method.")
        await super().start(*args, **kwargs)

    async def close(self, exit_code=0):
        self.logger.debug("RevBot: Received command to shut down. Beginning safe shutdown sequence.")
        self._exit_code = exit_code
        await self.cleanup()
        self.logger.debug("Closing connection to discord.")
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

    def Embed(self, **kwargs):
        if not ("color" in kwargs.keys() or "colour" in kwargs.keys()):
            kwargs['color'] = c if (c := getattr(self.properties, 'embed_color')) else discord.Color.blurple()
        return discord.Embed(**kwargs)


