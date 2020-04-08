
import discord
from discord.ext import commands, tasks

from collections import defaultdict

from utils import checks
from utils.db import Table
from utils.utility import module_logger

empty = {
    # meta
    'prefix': None,

    'ignore': {
        'channels': [],
        'users': [],
        'roles': [],
        'extensions': [],
        'commands': [],
    },
    'roles': {
        'administrator': [],
        'moderator': [],
        'muted': None,
        'claimable': {},
        'react': {},
        'autorole': [],
        # 'retain': [],
    },
    'modlog': {
        0: {
            # 'webhook': None,
            'mod-actions': [],
            'auto-actions': [],
            'events': [],
        },
    },
    'automod': {
        'blacklisted-content': [],
        'delete-server-invites': False,
        'delete-links': False,
        'punishment': None,
        'spam': False,
        'join-limit': False,
    },
}


class ConfigManager:
    def __init__(self, bot, cog):
        self.bot = bot
        self.table = bot.table
        self._configs = defaultdict(self.empty)
        self.logger = cog.logger

    @staticmethod
    def empty():
        config = defaultdict(lambda: None)
        # config['prefix'] = '+'
        #     {
        #     'admins': [],
        #     'mods': [],
        #     'claimable': {},
        #     'announcements': [],
        #     'autorole': []
        # }
        return config

    def read(self):
        try:
            data = self.table.read_to_dict('config')
            for guild_id, guild_config in data.items():
                self.get_config(guild_id).update(guild_config)
            return True
        except Exception as e:
            print(str(e))
            return False

    def write(self):
        try:
            self.update_names()
            self.table.write_from_dict(self._configs, 'config')
            return True
        except Exception:
            return False

    def write_guild(self, guild):
        try:
            self.update_name(guild.id)
            self.table.put(self.get_config(guild), [guild.id, 'config'])
            return True
        except Exception:
            return False

    def update_names(self):
        for guild_id in self.guilds():
            self.update_name(guild_id)

    def update_name(self, guild_id):
        guild = self.bot.get_guild(guild_id)
        if guild:
            self.get_config(guild)['name'] = guild.name

    def get_config(self, guild):
        if isinstance(guild, int):
            return self._configs[guild]
        elif isinstance(guild, discord.Guild):
            return self._configs[guild.id]
        else:
            raise TypeError("Argument 'guild' must be either a Guild or an integer.")

    def set_config(self, guild, new_config):
        self.get_config(guild).update(new_config)
        self.write_guild(guild)

    def reset_config(self, guild):
        if isinstance(guild, int):
            del self._configs[guild]
        elif isinstance(guild, discord.Guild):
            del self._configs[guild.id]
        else:
            raise TypeError("Argument 'guild' must be either a Guild or an integer.")

    def get_section(self, guild, section_name):
        return self.get_config(guild)[section_name]

    def edit_section(self, guild, section_name, new_data):
        self.get_config(guild)[section_name] = new_data
        self.write_guild(guild)

    def guilds(self):
        return list(self._configs.keys())


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = module_logger(self.bot._name, 'config')
        if not self.bot.table:
            raise Exception("Connection to DynamoDB table not found.")
        self.bot.config = ConfigManager(bot, self)
        self.config = self.bot.config
        c = self.config.read()
        if not c:
            raise Exception("Config could not be loaded from DynamoDB.")

    def cog_unload(self):
        c = self.config.write()
        if not c:
            self.logger.error("Error writing config to database.")

    @commands.Cog.listener()
    async def on_ready(self):
        # self.logger.info("Generating empty configs for non-configured guilds")
        # for guild in self.bot.guilds:
        #     self.config.check_config(guild)
        self.config.update_names()

    # @commands.Cog.listener()
    # async def on_guild_join(self, guild):
    #     self.config.check_config(guild)

    @commands.command()
    @checks.bot_admin()
    async def prefix(self, ctx, new_prefix=None):
        """Change the bot's prefix in this guild."""
        config = self.config.get_config(ctx.guild)
        # respond with current prefix
        if not new_prefix:
            current_prefix = self.bot.command_prefix(self.bot, ctx.message, True)
            await ctx.send(f"My prefix in this guild is `{current_prefix}`")
            return
        # set prefix
        if len(new_prefix) > 5:
            await ctx.send("Prefix can only be up to 5 characters!")
            return
        config['prefix'] = new_prefix
        await ctx.send(f"Prefix set to `{new_prefix}`")


def setup(bot):
    bot.add_cog(Config(bot))
