import yaml
import logging
from argparse import ArgumentParser

from discord.ext import commands

from bots import evalbot, bulbe, marvin, revbot
from utils import checks
from authentication import authentication
from utils.utility import setup_logger, module_logger


class Debug(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @checks.bot_admin()
    async def __kill(self, ctx):
        await ctx.send("Closing bot.")
        await self.bot.close()

    @commands.command()
    async def __test(self, ctx):
        await ctx.send("hello.")

    @commands.command()
    async def __ping(self, ctx, bot):
        m = await ctx.send("Pinging...")
        result = await self.bot.ping(bot)
        if result:
            p1, p2 = result
        else:
            p1, p2 = None, None
        if p1 is not None:
            p1 = f"`{p1:.4}s`"
        if p2 is not None:
            p2 = f"`{p2:.4}s`"
        await m.edit(content=f"Pong! {p1}, {p2}")


def start(name, debug, use_socket):
    if name == "marvin":
        start_marvin(debug)
    else:
        start_bot(name, use_socket)


def start_marvin(debug=False):
    logger = setup_logger("marvin")
    marv = marvin.Marvin(logger)
    try:
        marv.run(debug=debug)
    finally:
        marv.logger.info("Bot closed.")
        exit(0)


def start_bot(name, use_socket=True):
    logger = setup_logger(name)
    module_logger(name, 'discord', logging.INFO)

    logger.info(f"Starting {name}.")

    with open("configs/marvin.yaml") as f:
        _info = yaml.load(f, yaml.Loader)

    if name in _info['launcher'].keys():
        classname = _info['launcher'][name]
    else:
        classname = _info['launcher']['default']

    bot = None

    # if classname == 'discord.Client':
    #     pass
    # elif classname == 'commands.Bot':
    #     pass

    if classname == 'revbot.RevBot':
        bot = revbot.RevBot(command_prefix='__', name=name, logger=logger)
    elif classname == 'bulbe.Bulbe':
        bot = bulbe.Bulbe(name=name, logger=logger, use_socket=use_socket)
    elif classname == 'evalbot.EvalBot':
        bot = evalbot.EvalBot()
    else:
        logger.error("No class found. Closing.")
        exit(0)

    try:
        bot.add_cog(Debug(bot))
        bot.add_cog(evalbot.EvalCog(bot))
        bot.run(authentication.tokens[name])
    finally:
        logger.info("Bot closed.")
        exit(0)


def main():

    parser = ArgumentParser(description="Start a bot")
    parser.add_argument('bot')
    parser.add_argument('--debug', '-d', action='store_true')
    parser.add_argument('--no-socket', '-ns', action='store_false')

    args = parser.parse_args()

    start(args.bot, args.debug, args.no_socket)


if __name__ == "__main__":
    main()
