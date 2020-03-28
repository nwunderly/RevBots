
import asyncio
import subprocess

import discord
from discord.ext import commands

from utils import paginator
from bots.revbot import RevBot
from bots.evalbot import EvalCog


class Clippy(RevBot):
    def __init__(self, logger=None, command_prefix="systemctl ", **kwargs):
        super().__init__("Clippy", logger=logger, command_prefix=command_prefix, case_insensitive=True,
                         description="Clippy, professional bot manager", **kwargs)
        self._nwunder = None
        self.properties = None
        self.table = None

    async def on_ready(self):
        self.logger.info('Logged in as {0.user}.'.format(self))
        self._nwunder = await self.fetch_user(204414611578028034)

        self.logger.info("Bot is ready.")

    async def setup(self):
        self.add_cog(Systemd(self))

    async def cleanup(self):
        pass


class Systemd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def run_process(self, command):
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await process.communicate()
        except NotImplementedError:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await self.bot.loop.run_in_executor(None, process.communicate)

        return [output.decode() for output in result]

    @commands.command()
    @commands.is_owner()
    async def sh(self, ctx, *, command):
        """Runs a shell command."""

        async with ctx.typing():
            stdout, stderr = await self.run_process(command)

        if stderr:
            text = f'stdout:\n{stdout}\nstderr:\n{stderr}'
        else:
            text = stdout

        try:
            pages = paginator.TextPages(ctx, text)
            await pages.paginate()
        except Exception as e:
            await ctx.send(str(e))

    @commands.command()
    @commands.is_owner()
    async def start(self, ctx, who):

        cmd = f"systemctl start {who}"

        async with ctx.typing():
            stdout, stderr = await self.run_process(cmd)

        if stderr:
            text = f'stdout:\n{stdout}\nstderr:\n{stderr}'
        else:
            text = stdout

        try:
            pages = paginator.TextPages(ctx, text)
            await pages.paginate()
        except Exception as e:
            await ctx.send(str(e))

    @commands.command()
    @commands.is_owner()
    async def stop(self, ctx, who):

        cmd = f"systemctl stop {who}"

        async with ctx.typing():
            stdout, stderr = await self.run_process(cmd)

        if stderr:
            text = f'stdout:\n{stdout}\nstderr:\n{stderr}'
        else:
            text = stdout

        try:
            pages = paginator.TextPages(ctx, text)
            await pages.paginate()
        except Exception as e:
            await ctx.send(str(e))

    @commands.command()
    @commands.is_owner()
    async def status(self, ctx, who):

        cmd = f"systemctl status {who}"

        async with ctx.typing():
            stdout, stderr = await self.run_process(cmd)

        if stderr:
            text = f'stdout:\n{stdout}\nstderr:\n{stderr}'
        else:
            text = stdout

        try:
            pages = paginator.TextPages(ctx, text)
            await pages.paginate()
        except Exception as e:
            await ctx.send(str(e))

    @commands.command()
    @commands.is_owner()
    async def restart(self, ctx, who):

        cmd = f"systemctl restart {who}"

        async with ctx.typing():
            stdout, stderr = await self.run_process(cmd)

        if stderr:
            text = f'stdout:\n{stdout}\nstderr:\n{stderr}'
        else:
            text = stdout

        try:
            pages = paginator.TextPages(ctx, text)
            await pages.paginate()
        except Exception as e:
            await ctx.send(str(e))




