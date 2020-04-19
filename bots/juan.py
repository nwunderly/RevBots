
import discord
from discord.ext import tasks, commands

import yaml
import os
import datetime
import random
import collections

# custom imports
from bots.revbot import RevBot
from utils.db import Table
from utils import juan_checks as checks
from utils import utility


properties_fields = ['name', 'version', 'prefix', 'table', 'guild', 'channels', 'cogs', 'perms']
Properties = collections.namedtuple("Properties", properties_fields)


class Juandissimo(RevBot):
    def __init__(self, logger, **kwargs):
        super().__init__(name='juan', command_prefix='>', logger=logger, **kwargs)
        self.properties = Properties(*list(None for _ in properties_fields))
        self.table = None
        self.add_check(checks.global_check)

    async def on_ready(self):
        self.logger.info('Logged in as {0.user}.'.format(self))

    async def on_message(self, message):
        if message.guild.id not in [self.properties.guild, 537043976562409482]:
            return
        await super().on_message(message)

    async def setup(self):  # async method called before logging into discord
        self.logger.info("Setting up.")
        p = await self.read_properties()
        if not p:
            self.logger.error("Error reading properties. Exiting.")
            await self.close()
        self.table = Table(self.properties.table)
        self.logger.info("Loading cogs.")
        for cog in self.properties.cogs:
            try:
                self.load_extension(cog)
                self.logger.info(f"Loaded cog {cog}.")
            except commands.ExtensionError:
                self.logger.error(f"Error loading cog {cog}:", exc_info=True)
        self.logger.info("Done setting up.")

    async def read_properties(self):
        try:
            if (filename := f"juan.yaml") in os.listdir(utility.HOME_DIR + "/configs"):
                with open(utility.HOME_DIR + "/configs/" + filename) as f:
                    p = yaml.load(f, yaml.Loader)
                    self.properties = Properties(**p)
                return True
            return False
        except yaml.YAMLError:
            return False






