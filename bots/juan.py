# version 2.0.0

import discord
from discord.ext import tasks, commands

import yaml
import os
import datetime
import random

# custom imports
from bots.revbot import RevBot
from utils.aws import Table


class Juandissimo(RevBot):
    def __init__(self, logger, **kwargs):
        super().__init__(name='juan', command_prefix='>', logger=logger, **kwargs)
        self._properties = dict()
        self.table = None

    async def on_ready(self):
        self.logger.info('Logged in as {0.user}.'.format(self))

    async def setup(self):  # async method called before logging into discord
        self.logger.info("Setting up.")
        p = await self.read_properties()
        if not p:
            self.logger.error("Error reading properties. Exiting.")
            await self.close()
        self.table = Table(self._properties['table'])
        self.logger.info("Loading cogs.")
        for cog in self._properties['cogs']:
            try:
                self.load_extension(cog)
                self.logger.info(f"Loaded cog {cog}.")
            except commands.ExtensionError:
                self.logger.error(f"Error loading cog {cog}:", exc_info=True)
        self.logger.info("Done setting up.")

    async def read_properties(self):
        try:
            if (filename := f"juan.yaml") in os.listdir("configs"):
                with open("configs/" + filename) as f:
                    self._properties = yaml.load(f, yaml.Loader)
            return True
        except yaml.YAMLError:
            return False






