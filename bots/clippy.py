
import io
import asyncio
import subprocess
import traceback
import textwrap
import contextlib
import datetime

import discord
from discord.ext import commands

from utils import paginator
from bots.revbot import RevBot
from bots.evalbot import EvalCog


VERSION = "2.1.1"


class Clippy(RevBot):
    def __init__(self, logger=None, command_prefix="//", **kwargs):
        super().__init__("Clippy", logger=logger, command_prefix=command_prefix, case_insensitive=True,
                         description="Clippy, professional bot manager", **kwargs)
        self._nwunder = None
        self.table = None
        self.version = VERSION

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
        self._last_result = None

    async def run_process(self, command):
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await process.communicate()
        except NotImplementedError:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await self.bot.loop.run_in_executor(None, process.communicate)

        return [output.decode() for output in result]

    @staticmethod
    def cleanup_code(content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    @commands.is_owner()
    @commands.command(pass_context=True, name='eval', aliases=['python', 'run'])
    async def _eval(self, ctx, *, body: str):
        """Runs arbitrary python code"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_ret': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with contextlib.redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            # try:
            #     await ctx.message.add_reaction('😎')
            # except:
            #     pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```')

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




