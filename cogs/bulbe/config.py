
import discord
from discord import Member, TextChannel, Role
from discord.ext import commands, tasks

from collections import defaultdict
from typing import Union, Optional
import traceback

from utils import checks
from utils.db import Table
from utils.utility import module_logger, green_tick, red_tick
from utils.converters import Module, Command

DEFAULT_CONFIG = {
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
    },

    'muted-role': None,

    'utilities': {
        # 'claimable': dict(),
        # 'react': dict(),
        'autorole': list(),
        'persist': list(),
    },

    # 'modlog': {
    #     0: {
    #         # 'webhook': None,
    #         'mod-actions': list(),
    #         'auto-actions': list(),
    #         'events': list(),
    #     },
    # },

    # 'automod': {
    #     'blacklisted-content': list(),
    #     'delete-server-invites': False,
    #     'delete-links': False,
    #     'punishment': None,
    #     'spam': False,
    #     'join-limit': False,
    # },
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
        config.update(DEFAULT_CONFIG)
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

    def is_ignored(self, ctx):
        """Returns True if the channel, user, or one of the user's roles should be ignored."""
        ignored = self.get_config(ctx.guild)['ignored']
        if ignored is None or not isinstance(ignored, dict):
            return False
        try:
            if ctx.channel.id in ignored['channels']:
                return True
        except KeyError:
            pass
        except AttributeError:
            pass
        try:
            if ctx.author.id in ignored['users']:
                return True
        except KeyError:
            pass
        except AttributeError:
            pass
        try:
            for role in ctx.author.roles:
                if role.id in ignored['roles']:
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
            config = False
            for key, value in self.config.get_config(ctx.guild).items():
                if key not in ('name', 'guildID', 'dataType') and value != DEFAULT_CONFIG[key]:
                    config = True
                    s += f"{key}: {value}\n"
            s += "```"
            if config:
                await ctx.send(s)
            else:
                await ctx.send_help(self.configure_bot)

    @configure_bot.command()
    @checks.edit_config()
    async def prefix(self, ctx, new_prefix=None):
        """Change the bot's prefix in this guild."""
        # respond with current prefix
        if not new_prefix:
            current_prefix = self.bot.command_prefix(self.bot, ctx.message, True)
            await ctx.send(f"My prefix in this guild is `{current_prefix}`")
            return
        # set prefix
        if len(new_prefix) > 5:
            await ctx.send(f"{red_tick} Prefix can only be up to 5 characters!")
            return
        # config['prefix'] = new_prefix
        self.config.edit_section(ctx.guild.id, 'prefix', new_prefix)
        await ctx.send(f"{green_tick} Prefix set to `{new_prefix}`")

    @configure_bot.command()
    @checks.edit_config()
    async def ignore(self, ctx, target: Union[TextChannel, Member, Role]):
        """Sets bot to ignore commands by certain users, users with certain roles, or in a certain channel."""
        config = self.config.get_config(ctx.guild)
        ignored = config['ignored']
        if ignored is None:
            ignored = dict()
            ignored.update(DEFAULT_CONFIG['ignored'])

        if isinstance(target, TextChannel):
            if target.id in ignored['channels']:
                await ctx.send(f"{red_tick} Channel `{target.name}` is already in ignore list!")
                return
            ignored['channels'].append(target.id)
            self.config.edit_section(ctx.guild, 'ignored', ignored)
            await ctx.send(f"{green_tick} I will ignore channel `{target.name}` in this guild.")
            return

        elif isinstance(target, Member):
            if target.id in ignored['users']:
                await ctx.send(f"{red_tick} User `{target.name}` is already in ignore list!")
                return
            ignored['channels'].append(target.id)
            self.config.edit_section(ctx.guild, 'ignored', ignored)
            await ctx.send(f"{green_tick} I will ignore user `{target.name}` in this guild.")
            return

        elif isinstance(target, Role):
            if target.id in ignored['channels']:
                await ctx.send(f"{red_tick} Role `{target.name}` is already in ignore list!")
                return
            ignored['channels'].append(target.id)
            self.config.edit_section(ctx.guild, 'ignored', ignored)
            await ctx.send(f"{green_tick} I will ignore role `{target.name}` in this guild.")
            return

    @configure_bot.command()
    @checks.edit_config()
    async def unignore(self, ctx, target: Union[TextChannel, Member, Role]):
        """Removes a user, role, or channel from this guild's ignored list."""
        config = self.config.get_config(ctx.guild)
        ignored = config['ignored']
        if ignored is None:
            ignored = dict()
            ignored.update(DEFAULT_CONFIG['ignored'])

        if isinstance(target, TextChannel):
            if target.id not in ignored['channels']:
                await ctx.send(f"{red_tick} Channel `{target.name}` is not in ignore list!")
                return
            ignored['channels'].remove(target.id)
            self.config.edit_section(ctx.guild, 'ignored', ignored)
            await ctx.send(f"{green_tick} I will no longer ignore channel `{target.name}` in this guild.")
            return

        elif isinstance(target, Member):
            if target.id not in ignored['users']:
                await ctx.send(f"{red_tick} User `{target.name}` is not in ignore list!")
                return
            ignored['channels'].remove(target.id)
            self.config.edit_section(ctx.guild, 'ignored', ignored)
            await ctx.send(f"{green_tick} I will no longer ignore user `{target.name}` in this guild.")
            return

        elif isinstance(target, Role):
            if target.id not in ignored['channels']:
                await ctx.send(f"{red_tick} Role `{target.name}` is not in ignore list!")
                return
            ignored['channels'].remove(target.id)
            self.config.edit_section(ctx.guild, 'ignored', ignored)
            await ctx.send(f"{green_tick} I will no longer ignore role `{target.name}` in this guild.")
            return

    @configure_bot.command()
    @checks.edit_config()
    async def disable(self, ctx, target: Union[Module, Command]):
        """Disables a command (or every command in a module) in this guild."""
        if target and "config" in target.qualified_name.lower():
            await ctx.send(f"{red_tick} You can't disable the Config module or any of its commands!")
            return
        config = self.config.get_config(ctx.guild)
        disabled = config['disabled']
        if disabled is None:
            disabled = dict()
            disabled.update(DEFAULT_CONFIG['disabled'])

        if isinstance(target, commands.Cog):
            if target.qualified_name in disabled['modules']:
                await ctx.send(f"{red_tick} Module `{target.qualified_name}` is already disabled!")
                return
            disabled['modules'].append(target.qualified_name)
            self.config.edit_section(ctx.guild, 'disabled', disabled)
            await ctx.send(f"{green_tick} Disabled module `{target.qualified_name}` for this guild.")
            return

        elif isinstance(target, commands.Command):
            if target.qualified_name in disabled['commands']:
                await ctx.send(f"{red_tick} Command `{target.qualified_name}` is already disabled!")
                return
            disabled['commands'].append(target.qualified_name)
            self.config.edit_section(ctx.guild, 'disabled', disabled)
            await ctx.send(f"{green_tick} Disabled command `{target.qualified_name}` for this guild.")
            return

    @configure_bot.command()
    @checks.edit_config()
    async def enable(self, ctx, target: Union[Module, Command]):
        """Enables a disabled command (or every command in a module) in this guild."""
        config = self.config.get_config(ctx.guild)
        disabled = config['disabled']
        if disabled is None:
            disabled = dict()
            disabled.update(DEFAULT_CONFIG['disabled'])

        if isinstance(target, commands.Cog):
            if target.qualified_name not in disabled['modules']:
                await ctx.send(f"{red_tick} Module `{target.qualified_name}` is not disabled!")
                return
            disabled['modules'].remove(target.qualified_name)
            self.config.edit_section(ctx.guild, 'disabled', disabled)
            await ctx.send(f"{green_tick} Enabled module `{target.qualified_name}` for this guild.")
            return

        elif isinstance(target, commands.Command):
            if target.qualified_name not in disabled['commands']:
                await ctx.send(f"{red_tick} Command `{target.qualified_name}` is not disabled!")
                return
            disabled['commands'].remove(target.qualified_name)
            self.config.edit_section(ctx.guild, 'disabled', disabled)
            await ctx.send(f"{green_tick} Enabled command `{target.qualified_name}` for this guild.")
            return

    @configure_bot.group(aliases=['ar'])
    @checks.edit_config()
    async def autorole(self, ctx):
        """Edit this guild's autoroles."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.autorole)

    @autorole.command(name='add', aliases=['a'])
    @checks.edit_config()
    async def autorole_add(self, ctx, role: discord.Role):
        """Adds a role to autorole list."""
        if role.id == ctx.guild.id:
            await ctx.send("Invalid role.")

        config = self.config.get_config(ctx.guild)
        utilities = config['utilities']
        if utilities is None:
            utilities = dict()
            utilities.update(DEFAULT_CONFIG['utilities'])

        if role.id in utilities['autorole']:
            await ctx.send(f"{red_tick} Role `{role.name}` is already a configured autorole!")

        else:
            utilities['autorole'].append(role.id)
            self.config.edit_section(ctx.guild, 'utilities', utilities)
            await ctx.send(f"{green_tick} Added `{role.name}` to autoroles.")

    @autorole.command(name='remove', aliases=['rm', 'r'])
    @checks.edit_config()
    async def autorole_remove(self, ctx, role: discord.Role):
        """Removes a role from autorole list."""
        if role.id == ctx.guild.id:
            await ctx.send("Invalid role.")

        config = self.config.get_config(ctx.guild)
        utilities = config['utilities']
        if utilities is None:
            utilities = dict()
            utilities.update(DEFAULT_CONFIG['utilities'])

        if role.id not in utilities['autorole']:
            await ctx.send(f"{red_tick} Role `{role.name}` is not a configured autorole!")

        else:
            utilities['autorole'].remove(role.id)
            self.config.edit_section(ctx.guild, 'utilities', utilities)
            await ctx.send(f"{green_tick} Removed `{role.name}` from autoroles.")

    @configure_bot.group(aliases=['ps'])
    @checks.edit_config()
    async def persist(self, ctx):
        """Edit role persist for this guild."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.persist)

    @persist.command(name='add', aliases=['a'])
    @checks.edit_config()
    async def persist_add(self, ctx, role: discord.Role):
        """Adds a role to role persist."""
        if role.id == ctx.guild.id:
            await ctx.send("Invalid role.")

        config = self.config.get_config(ctx.guild)
        utilities = config['utilities']
        if utilities is None:
            utilities = dict()
            utilities.update(DEFAULT_CONFIG['utilities'])

        if role.id in utilities['persist']:
            await ctx.send(f"{red_tick} Role `{role.name}` is already a configured persist role!")

        else:
            utilities['persist'].append(role.id)
            self.config.edit_section(ctx.guild, 'utilities', utilities)
            await ctx.send(f"{green_tick} Added `{role.name}` to persist roles.")

    @persist.command(name='remove', aliases=['rm', 'r'])
    @checks.edit_config()
    async def persist_remove(self, ctx, role: discord.Role):
        """Removes a role from role persist."""
        if role.id == ctx.guild.id:
            await ctx.send("Invalid role.")

        config = self.config.get_config(ctx.guild)
        utilities = config['utilities']
        if utilities is None:
            utilities = dict()
            utilities.update(DEFAULT_CONFIG['utilities'])

        if role.id not in utilities['persist']:
            await ctx.send(f"{red_tick} Role `{role.name}` is not a configured persist role!")

        else:
            utilities['persist'].remove(role.id)
            self.config.edit_section(ctx.guild, 'utilities', utilities)
            await ctx.send(f"{green_tick} Removed `{role.name}` from persist roles.")


def setup(bot):
    bot.add_cog(Config(bot))
