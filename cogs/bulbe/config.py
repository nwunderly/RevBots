
import discord
from discord import Member, TextChannel, Role
from discord.ext import commands, tasks

from collections import defaultdict
from typing import Union, Optional
import traceback

from utils import checks
from utils.db import Table
from utils.utility import module_logger
from utils.converters import Module, Command

empty = {
    # meta
    'prefix': None,

    'ignored': {
        'channels': list(),
        'users': list(),
        'roles': list(),
    },
    'disabled': {
        'modules': list(),
        'commands': list(),
    },
    'roles': {
        'administrator': list(),
        'moderator': list(),
        'muted': None,
        'claimable': dict(),
        'react': dict(),
        'autorole': list(),
        # 'retain': [],
    },
    'modlog': {
        0: {
            # 'webhook': None,
            'mod-actions': list(),
            'auto-actions': list(),
            'events': list(),
        },
    },
    'automod': {
        'blacklisted-content': list(),
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
            traceback.print_exc()
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

    # def get_section(self, guild, section_name):
    #     return self.get_config(guild)[section_name]

    def edit_section(self, guild, section_name, new_data):
        section = self.get_config(guild)[section_name]
        if isinstance(section, dict):
            section.update(new_data)
        else:
            self.get_config(guild)[section_name] = new_data
        self.write_guild(guild)

    def guilds(self):
        return list(self._configs.keys())

    def command_disabled(self, ctx):
        """Returns True if the command has been disabled."""
        disabled = self.get_config(ctx.guild)['disabled']
        if disabled is None or not isinstance(disabled, dict):
            return False
        try:
            if ctx.cog.qualified_name in disabled['modules']:
                return True
        except KeyError:
            pass
        except AttributeError:
            pass
        try:
            if ctx.command.qualified_name in disabled['commands']:
                return True
        except KeyError:
            pass
        except AttributeError:
            pass
        return False


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

    @commands.group(name='config')
    @checks.edit_config()
    async def configure_bot(self, ctx):
        """Edit this guild's configuration."""
        if ctx.invoked_subcommand is None:
            s = "**Current Config:**```\n"
            for key, value in self.config.get_config(ctx.guild).items():
                s += f"{key}: {value}\n"
            s += "```"
            await ctx.send(s)

    @configure_bot.command()
    @checks.edit_config()
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
        # config['prefix'] = new_prefix
        self.config.edit_section(ctx.guild.id, 'prefix', new_prefix)
        await ctx.send(f"Prefix set to `{new_prefix}`")

    @configure_bot.command()
    @checks.edit_config()
    async def ignore(self, ctx, target: Union[TextChannel, Member, Role] = None):
        """Sets bot to ignore commands by certain users, users with certain roles, or in a certain channel."""
        config = self.config.get_config(ctx.guild)
        if not target:
            pass  # todo
        elif isinstance(target, TextChannel):
            pass  # todo
        elif isinstance(target, Member):
            pass  # todo
        elif isinstance(target, Role):
            pass  # todo

    @configure_bot.command()
    @checks.edit_config()
    async def disable(self, ctx, target: Union[Module, Command]):
        """Disables a command (or every command in a module) in this guild."""
        if target and "config" in target.qualified_name.lower():
            await ctx.send("You can't disable the Config module or any of its commands!")
            return
        config = self.config.get_config(ctx.guild)
        disabled = config['disabled']
        if disabled is None:
            disabled = dict()
        if isinstance(target, commands.Cog):
            if 'modules' not in disabled.keys() or not isinstance(disabled['modules'], list):
                disabled['modules'] = list()
            if target.qualified_name in disabled['modules']:
                await ctx.send(f"Module `{target.qualified_name}` is already disabled!")
                return
            disabled['modules'].append(target.qualified_name)
            self.config.edit_section(ctx.guild, 'disabled', disabled)
            await ctx.send(f"Disabled module `{target.qualified_name}` for this guild.")
            return
        elif isinstance(target, commands.Command):
            if 'commands' not in disabled.keys() or not isinstance(disabled['commands'], list):
                disabled['commands'] = list()
            if target.qualified_name in disabled['commands']:
                await ctx.send(f"Command `{target.qualified_name}` is already disabled!")
                return
            disabled['commands'].append(target.qualified_name)
            self.config.edit_section(ctx.guild, 'disabled', disabled)
            await ctx.send(f"Disabled command `{target.qualified_name}` for this guild.")
            return

    @configure_bot.command()
    @checks.edit_config()
    async def enable(self, ctx, target: Union[Module, Command]):
        """Enables a disabled command (or every command in a module) in this guild."""
        config = self.config.get_config(ctx.guild)
        disabled = config['disabled']
        if disabled is None:
            disabled = dict()
        if isinstance(target, commands.Cog):
            if 'modules' not in disabled.keys() or not isinstance(disabled['modules'], list):
                disabled['modules'] = list()
            if target.qualified_name not in disabled['modules']:
                await ctx.send(f"Module `{target.qualified_name}` is not disabled!")
                return
            disabled['modules'].remove(target.qualified_name)
            self.config.edit_section(ctx.guild, 'disabled', disabled)
            await ctx.send(f"Enabled module `{target.qualified_name}` for this guild.")
            return
        elif isinstance(target, commands.Command):
            if 'commands' not in disabled.keys() or not isinstance(disabled['commands'], list):
                disabled['commands'] = list()
            if target.qualified_name not in disabled['commands']:
                await ctx.send(f"Command `{target.qualified_name}` is not disabled!")
                return
            disabled['commands'].remove(target.qualified_name)
            self.config.edit_section(ctx.guild, 'disabled', disabled)
            await ctx.send(f"Enabled command `{target.qualified_name}` for this guild.")
            return


def setup(bot):
    bot.add_cog(Config(bot))
