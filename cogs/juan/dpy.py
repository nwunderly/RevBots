
import io
import aiohttp

import discord
from discord import Webhook
from discord import AsyncWebhookAdapter
from discord.ext import commands

from utils import checks
from authentication.captain_hook import webhooks


class DamnDanny(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.hook = webhooks['dpy']

    async def webhook(self, message, text=None):
        files = list()
        for a in message.attachments:
            files.append(io.BytesIO(await a.read()))
        text = text if text else message.clean_content
        async with aiohttp.ClientSession() as session:
            webhook = Webhook.from_url(self.hook, adapter=AsyncWebhookAdapter(session))
            await webhook.send(text, files=files)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id == 381965829857738772:
            self.logger.info("Detected announcement in discord.py server, sending webhook.")
            await self.webhook(message)

    @commands.command()
    @commands.is_owner()
    async def set_webhook(self, ctx, *, url):
        if url == 'reset':
            self.hook = webhooks['dpy']
        else:
            self.hook = url
        await ctx.send(f"Changed webhook url to `{self.hook}`.")

    @commands.command()
    @commands.is_owner()
    async def test_webhook(self, ctx, *, things: commands.clean_content):
        self.logger.info(f"Discord.py test_webhook command invoked by {ctx.author}.")
        await self.webhook(ctx.message, text=things)


def setup(bot):
    bot.add_cog(DamnDanny(bot))

