
import datetime
import io
import asyncio
import subprocess
import textwrap
import contextlib
import traceback
import typing
import copy

import discord
from discord.ext import commands

from utils import juan_checks as checks
from utils import converters
from utils import paginator


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None

    async def cog_check(self, ctx):
        return await ctx.bot.is_owner(ctx.author)

    @commands.Cog.listener()
    async def on_message(self, message):
        pass

    @commands.command()
    async def test(self, ctx):
        await ctx.send(f"Online and functional. <:juandissimo:570424731501723648>\n"
                       f"Online for: {datetime.datetime.now() - self.bot.started_at}\n"
                       f"Cogs: {', '.join(list(self.bot.cogs.keys()))}")

    @commands.command()
    async def close(self, ctx):
        await ctx.send("Closing.")
        await self.bot.close()

    @staticmethod
    def cleanup_code(content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    async def run_process(self, command):
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await process.communicate()
        except NotImplementedError:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await self.bot.loop.run_in_executor(None, process.communicate)

        return [output.decode() for output in result]

    @commands.command(pass_context=True, name='eval', aliases=['e', 'py'])
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

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```')

    @commands.command()
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
    async def load(self, ctx, *, cog):
        """Loads a cog."""
        try:
            self.bot.load_extension(cog)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send(f'Loaded {cog}.')

    @commands.command()
    async def unload(self, ctx, *, cog):
        """Unloads a cog."""
        try:
            self.bot.unload_extension(cog)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send(f'Unloaded {cog}.')

    @commands.command(name='reload')
    async def _reload(self, ctx, *, cog):
        """Reloads a cog."""
        try:
            self.bot.reload_extension(cog)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send(f'Reloaded {cog}.')

    @commands.command()
    async def sudo(self, ctx, channel: typing.Optional[converters.GlobalChannel], who: discord.User, *, command: str):
        """Run a command as another user in another channel."""
        msg = copy.copy(ctx.message)
        channel = channel or ctx.channel
        msg.channel = channel
        msg.author = channel.guild.get_member(who.id) or who
        msg.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(msg, cls=type(ctx))
        await self.bot.invoke(new_ctx)

    @commands.command()
    async def repeat(self, ctx, times: int, *, command):
        """Repeats a command."""
        msg = copy.copy(ctx.message)
        msg.content = ctx.prefix + command

        new_ctx = await self.bot.get_context(msg, cls=type(ctx))

        for i in range(times):
            await new_ctx.reinvoke()



def setup(bot):
    bot.add_cog(Admin(bot))
