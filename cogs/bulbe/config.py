
import discord
from discord.ext import commands

from utils.aws import Table
from utils.utility import module_logger

empty = {
    # meta
    'prefix': None,
    'extensions': None,
    'commands': None,

    'ignore': {
        'channels': [],
        'users': [],
        'roles': [],
    },
    'moderation': {
        'administrator': [],
        'moderator': [],
        'trusted': [],
        'standard': [],
        'muted': None,
    },
    'roles': {
        'claimable': {},
        'react': {},
        'announcement': [],
        'autorole': [],
        # 'retain': [],
    },
    'modlog': {
        0: {
            'webhook': None,
            'mod-actions': [],
            'auto-actions': [],
            'events': [],
        },
    },
    'automod': {
        'blacklisted-content': [],
        'delete-server-invites': False,
        'delete-links': False,
        'punishment': (),
        'spam': False,
        'join-limit': False,
    },
}


def empty_config():
    return {}
    #     {
    #     'admins': [],
    #     'mods': [],
    #     'claimable': {},
    #     'announcements': [],
    #     'autorole': []
    # }


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = module_logger(self.bot._name, 'config')
        self.bot._config = {}
        if not self.bot.table:
            raise Exception("Connection to DynamoDB table not found.")
        c = self.read_config()
        if not c:
            raise Exception("Config could not be loaded from DynamoDB.")

    def generate_empty_config(self, guild):
        self.bot._config[guild.id] = empty_config()

    def read_config(self):
        try:
            table = self.bot.table
            self.bot._config = table.read_to_dict('config')
            return True
        except Exception as e:
            print(str(e))
            self.bot._config = {}
            return False

    def write_config(self):
        for key in self.bot._config.keys():
            self.bot._config[key]['name'] = str(self.bot.get_guild(key))
        try:
            table = self.bot.table
            table.write_from_dict(self.bot._config, 'config')
            return True
        except Exception:
            return False

    def cog_unload(self):
        c = self.write_config()
        if not c:
            self.logger.error("Error writing config to database.")

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Generating empty configs for non-configured guilds")
        for guild in self.bot.guilds:
            if guild.id not in self.bot._config.keys():
                self.generate_empty_config(guild)
                self.logger.info(f"Generated empty config for guild {guild.name}.")
        empty = empty_config()
        for guild_id in self.bot._config.keys():
            updated = False
            for key in empty.keys():
                if key not in self.bot._config[guild_id].keys():
                    updated = True
                    self.bot._config[guild_id][key] = empty[key]
            if updated:
                guild = self.bot.get_guild(guild_id)
                self.logger.info(f"Updated config for guild {guild.name if guild else guild_id}.")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if guild.id not in self.bot._config.keys():
            self.logger.info(f"Could not find config for guild {guild.name}. Generating empty config.")
            self.generate_empty_config(guild)


def setup(bot):
    bot.add_cog(Config(bot))