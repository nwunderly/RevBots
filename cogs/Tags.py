from discord.ext import commands
# import yaml
from utils.paginator import Pages
from utils import mongo_setup


def tag_check(ctx, d: dict, tag):
    t = d.get(tag, None)
    if not t:
        return
    if t['author'] == ctx.author.id:
        return True, None
    else:
        return False, 'You do not have the permissions to delete this tag.'


class Tag(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage("Tag commands cannot be used in DMs")
        else:
            return True

    @commands.group(case_insensitive=True)
    async def tag(self, ctx):
        if ctx.invoked_subcommand is None:
            tag = ctx.message.content.replace(f"{ctx.prefix}{ctx.command.qualified_name}", '')
            tag = tag[1:len(tag)]
            # print(tag)
            if not tag:
                return await ctx.send("Please specify a Subcommand or tag")
            tags = mongo_setup.tags.find_one({'_id': ctx.guild.id})
            if not tags:
                return await ctx.send("This server has no tags yet")
            t = tags.get(tag, None)
            if not t:
                return await ctx.send(f"Tag {tag} does not exist for this server")
            await ctx.send(t['value'])

    @tag.command()
    async def create(self, ctx, tag_name: commands.clean_content, *, tag_value: commands.clean_content):
        tag_name = str(tag_name)
        if tag_name.lower() in ['remove', 'create']:
            return await ctx.send("Cannot make tag that is a tag command.")
        if len(tag_name.strip()) > 100:
            return await ctx.send("Tag name too long (100 or less characters)")
        if len(str(tag_value)) >= 1800:
            return await ctx.send("Tag value too long (1800 or less characters")
        g = mongo_setup.mod_and_logging_config.find_one({'_id': ctx.guild.id})
        if not g:
            mongo_setup.tags.insert_one({'_id': ctx.guild.id})
            g = mongo_setup.tags.find_one({'_id': ctx.guild.id})
        t = g.get(tag_name, None)
        if not t:
            d = {'value': tag_value,
                 'author': ctx.author.id}
            mongo_setup.tags.update_one({'_id': ctx.guild.id}, {'$set': {tag_name: d}})
            return await ctx.send(f"Tag {tag_name} created!")
        await ctx.send(f"Tag {tag_name} already exists")

    @tag.command()
    async def remove(self, ctx, tag_name):
        g = mongo_setup.tags.find_one({'_id': ctx.guild.id})
        if not g:
            return await ctx.send("This server has no tags")
        tag = g.get(tag_name, None)
        if not tag:
            return await ctx.send(f"Tag {tag_name} does not exist")
        can_delete, message_if_cant = tag_check(ctx, g, tag_name)
        if message_if_cant:
            return await ctx.send(message_if_cant)
        g.pop(tag_name)
        mongo_setup.tags.update_one({'_id': ctx.guild.id}, {'$unset': tag_name})
        await ctx.send(f"Removed tag {tag_name}")

    @commands.command()
    async def tags(self, ctx):
        g = mongo_setup.tags.find_one({'_id': ctx.guild.id})
        if not g:
            return await ctx.send("This server has no tags yet.")
        tag_info = []
        for key, val in g.items():
            if not isinstance(val, dict):
                continue
            author = val['author']
            tag_info.append(f'Name: {key}\nAuthor: {self.bot.get_user(author)}')
        pages = Pages(ctx, entries=tag_info, specific_name=f'Tags for {ctx.guild.name}')
        await pages.paginate()


def setup(bot):
    bot.add_cog(Tag(bot))
