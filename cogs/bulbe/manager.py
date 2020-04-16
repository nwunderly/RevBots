
import asyncio

import discord
from discord.ext import commands

from utils import checks
from utils.utility import yellow_tick, green_tick, red_tick


class Manager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._invites = dict()

    @commands.group()
    @checks.bulbe_perms('manager')
    async def guild(self, ctx):
        await ctx.send_help(self.guild)

    @guild.command()
    @checks.bulbe_perms('manager')
    async def list(self, ctx):
        guilds = sorted(self.bot.guilds, key=lambda g: len(g.members), reverse=True)
        s = f"**{len(guilds)} guilds:**"
        for g in guilds:
            s += f"\n[`{g.id}`]  {g.name}  [{len(g.members)}]"
        await ctx.send(s)

    @guild.command()
    @checks.bulbe_perms('manager')
    async def leave(self, ctx, guild_id: int = None):
        guild = self.bot.get_guild(guild_id) if guild_id else ctx.guild
        if not guild:
            await ctx.send(f"{red_tick} Guild not found.")
            return
        await ctx.send(f"{yellow_tick} Are you sure you want me to leave {guild.name}?")
        try:
            msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=5)
        except asyncio.TimeoutError:
            await ctx.send(f"{red_tick} Timed out.")
            return
        if msg.content.lower().startswith('y'):
            msg_2 = await ctx.send("Leaving guild...")
            await guild.leave()
            try:
                await msg_2.edit(content=f"{green_tick} Left guild!")
            except discord.NotFound:
                pass
        else:
            await ctx.send(f"{red_tick} Action canceled.")

    @guild.command()
    @checks.bulbe_perms('manager')
    async def info(self, ctx, guild_id: int = None):
        guild = self.bot.get_guild(guild_id) if guild_id else ctx.guild
        if not guild:
            await ctx.send(f"{red_tick} Guild not found.")
            return

        def with_permission(permission):
            return list(filter(lambda m: getattr(m.guild_permissions, permission) and not m.bot, guild.members))

        def bot(_bool):
            return list(filter(lambda m: m.bot == _bool, guild.members))

        s = f"**{guild.name}** [{guild.id}]\n" \
            f"Owner: {guild.owner.mention if guild.owner in ctx.guild.members else guild.owner} [{guild.owner.id}]\n" \
            f"Created: {guild.created_at}\n" \
            f"Added me: {guild.me.joined_at}\n" \
            f"Members: {len(bot(False))} humans, {len(bot(True))} bots\n" \
            f"Channels: {len(guild.text_channels)} text, {len(guild.voice_channels)} voice, {len(guild.categories)} categories\n" \
            f"Roles: {len(guild.roles)}\n" \
            f"Staff: {(a := len(with_permission('manage_guild')))} admins, {len(with_permission('ban_members'))-a} mods\n"

        embed = self.bot.Embed(description=s)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Manager(bot))
