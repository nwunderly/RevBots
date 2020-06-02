
import typing
import datetime
import aiohttp
import asyncio
import datetime

import discord
from discord.ext import commands

from google.cloud import translate_v2 as translate
from google.oauth2.service_account import Credentials

from authentication.authentication import cloud_creds, nasa_api_key
from utils.utility import HOME_DIR, fetch_previous_message, red_tick
from utils.converters import Language


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        credentials = Credentials.from_service_account_file(f"{HOME_DIR}/authentication/{cloud_creds}")
        self.translator = translate.Client(credentials=credentials)
        self.lang_cache = dict()
        self.session = aiohttp.ClientSession()

    @commands.command(name='translate', aliases=['t'])
    async def _translate(self, ctx, lang: typing.Optional[Language] = 'en', *, text: commands.clean_content = None):
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
            text = result['translatedText'].replace('&#39;', '\'')
            await ctx.send(f"(from {result['detectedSourceLanguage']}) {text}")

    @commands.command()
    async def lmgtfy(self, ctx, *, search):
        """Let me google that for you."""
        q = search.replace(" ", "+").replace("\n", "+")
        await ctx.send(f"https://lmgtfy.com/?q={q}")

    @commands.command()
    async def apod(self, ctx, *, date=None):
        """Astronomy picture of the day. Date format should be mm-dd-yyyy, mm/dd/yyyy."""
        if not date or (date and date.lower() == 'today'):
            date = datetime.datetime.today()
        elif date.lower() == 'yesterday':
            date = datetime.datetime.today() - datetime.timedelta(days=1)
        else:
            try:
                mmddyy = date.split('-')
                if len(mmddyy) == 1:
                    mmddyy = mmddyy.split('/')
                if len(mmddyy) == 1:
                    mmddyy = mmddyy.split(' ')
                if len(mmddyy) == 2:
                    mm, dd = [int(i) for i in mmddyy]
                    yy = 2020
                elif len(mmddyy) == 3:
                    mm, dd, yy = [int(i) for i in mmddyy]
                else:
                    raise ValueError
                date = datetime.date(year=yy, month=mm, day=dd)
                if not datetime.date(year=2015, month=1, day=1) <= date <= datetime.datetime.today():
                    raise ValueError
            except ValueError:
                await ctx.send(f"{red_tick} Error converting date. Please make sure you're using a supported format.")
                return
        api_formatted_date = f"{date.year}-{date.month}-{date.day}"
        site_formatted_date = f"{str(date.year)[2:]}{date.month:02d}{date.day:02d}"
        api_url = f"https://api.nasa.gov/planetary/apod?date={api_formatted_date}&api_key={nasa_api_key}"
        site_url = f"https://apod.nasa.gov/apod/ap{site_formatted_date}.html"
        response = await self.session.get(api_url)
        data = await response.json()
        title = f"{data['title']} ({data['date']})"
        await ctx.send(embed=self.bot.Embed(title=title, description=data['explanation'], url=site_url).set_image(url=data['hdurl']))


def setup(bot):
    bot.add_cog(Fun(bot))
