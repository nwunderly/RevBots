
import typing
import datetime

import discord
from discord.ext import commands

from google.cloud import translate_v2 as translate
from google.oauth2.service_account import Credentials

from authentication.authentication import cloud_creds
from utils.utility import HOME_DIR, fetch_previous_message, red_tick
from utils.converters import Language


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        credentials = Credentials.from_service_account_file(f"{HOME_DIR}/authentication/{cloud_creds}")
        self.translator = translate.Client(credentials=credentials)
        self.lang_cache = dict()

    @commands.command(name='translate', aliases=['t'])
    async def _translate(self, ctx, lang: typing.Optional[Language] = 'en', *, text=None):
        """Translates a message into a language of your choice.
        Defaults to English. If no text to translate is specified, uses the current channel's previous message."""
        if not lang:
            lang = 'en'
        if not text:
            prev = await fetch_previous_message(ctx.message)
            text = prev.content
        client = self.translator
        result = client.translate(text, target_language=lang)
        if isinstance(result, dict):
            await ctx.send(f"(from {result['detectedSourceLanguage']}) {result['translatedText']}")

    @commands.command()
    async def lmgtfy(self, ctx, *, search):
        """Let me google that for you."""
        q = search.replace(" ", "+").replace("\n", "+")
        await ctx.send(f"https://lmgtfy.com/?q={q}")

    @commands.command()
    async def apod(self, ctx, *, date=None):
        """Astronomy picture of the day. Date format should be mm/dd/yy, mm/dd/yyyy."""
        if not date or (date and date.lower() == 'today'):
            today = datetime.datetime.today()
            formatted_date = f"{str(today.year)[2:]}{today.month:02d}{today.day:02d}"
        elif date.lower() == 'yesterday':
            yesterday = datetime.datetime.today() - datetime.timedelta(days=1)
            formatted_date = f"{str(yesterday.year)[2:]}{yesterday.month:02d}{yesterday.day:02d}"
        else:
            try:
                mm, dd, yy = date.split('/')
                yy = yy if len(yy := str(yy)) == 2 else yy[2:]
                formatted_date = f"{yy}{int(mm):02d}{int(dd):02d}"
            except ValueError:
                await ctx.send(f"{red_tick} Error converting date. Please make sure you're using a supported format.")
                return
        url = f"https://apod.nasa.gov/apod/ap{formatted_date}.html"
        await ctx.send(url)


def setup(bot):
    bot.add_cog(Fun(bot))
