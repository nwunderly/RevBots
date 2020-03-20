# version 1.0

import discord
from discord.ext import commands, tasks
from discord.client import _cleanup_loop

import signal
import asyncio
import datetime
import systemd

# custom imports
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
        self.logger.info("Connecting to Marvin.")

    async def ping_response(self, channel):
        await channel.send(embed=discord.Embed(title=f"{self._name} ({datetime.datetime.now() - self.started_at})",
                                               description=f"Prefix: `{self.command_prefix}`"))

    async def on_message(self, message):
        if message.author.bot:
            return
        if (await self.is_owner(message.author)) and message.content in ['<@!572566171174305793>', '<@572566171174305793>']:
            await self.ping_response(message.channel)
        await self.process_commands(message)

    @tasks.loop(seconds=1)
    async def watchdog(self):
        systemd.daemon.notify("WATCHDOG=1")

    @staticmethod
    def sd_notify(arg):
        systemd.daemon.notify(arg)

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

    def run(self, *args, **kwargs):
        """
        Modified version of discord.py's bot.run() method.
        Use in exactly the same way.
        """
        loop = self.loop

        def terminate():
            if self.__future:
                self.__future.cancel()
            else:
                loop.close()

        try:
            loop.add_signal_handler(signal.SIGINT, lambda: terminate())
            loop.add_signal_handler(signal.SIGTERM, lambda: terminate())
        except NotImplementedError:
            pass

        async def runner():
            try:
                await self.setup()
                self.sd_notify("READY=1")
                self.watchdog.start()
                await self.start(*args, **kwargs)
            finally:
                await self.close()

        def stop_loop_on_completion():
            loop.stop()

        future = asyncio.ensure_future(runner(), loop=loop)
        future.add_done_callback(stop_loop_on_completion)
        self.__future = future

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            self.logger.info('Received signal to terminate bot and event loop.')
        finally:
            future.remove_done_callback(stop_loop_on_completion)
            self.logger.info('Cleaning up tasks.')
            _cleanup_loop(loop)

    async def close(self):
        self.logger.debug("RevBot: Received command to shut down. Beginning safe shutdown sequence.")
        await self.cleanup()
        self.logger.info("Closing connection to discord.")
        await super().close()

    # def kill(self):
    #     for extension in tuple(self.__extensions):
    #         try:
    #             self.unload_extension(extension)
    #         except Exception:
    #             pass
    #     for cog in tuple(self.__cogs):
    #         try:
    #             self.remove_cog(cog)
    #         except Exception:
    #             pass
    #     self.loop.close()

