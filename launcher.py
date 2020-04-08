
import sys
import yaml
import logging
from argparse import ArgumentParser

from discord.ext import commands

from bots import evalbot, bulbe, revbot, juan, clippy
# from bots import marvin
from utils import checks
from authentication import authentication
from utils.utility import setup_logger, module_logger, HOME_DIR


bots = {
    'bulbe': 'bulbe.Bulbe',
    'kippy': 'bulbe.Bulbe',
    'juan': 'juan.Juandissimo',
    'clippy': 'clippy.Clippy',
}


class Debug(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def __kill(self, ctx):
        await ctx.send("Closing bot.")
        await self.bot.close()

    @commands.command()
    async def __test(self, ctx):
        await ctx.send("hello.")


def start(name, debug=False):
    if sys.platform != 'linux' or debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    bot_logger = setup_logger(name)
    logger = module_logger(name, "launcher", level)
    module_logger(name, 'discord', logging.INFO)

    logger.info(f"Starting {name}.")

    if name in bots.keys():
        classname = bots[name]
    else:
        classname = None

    bot = None

    if classname == 'revbot.RevBot':
        logger.debug("RevBot class selected. Initializing.")
        bot = revbot.RevBot(command_prefix='__', name=name, logger=bot_logger)
    elif classname == 'bulbe.Bulbe':
        logger.debug("Bulbe class selected. Initializing.")
        bot = bulbe.Bulbe(name=name, logger=bot_logger)
    elif classname == 'evalbot.EvalBot':
        logger.debug("EvalBot class selected. Initializing.")
        bot = evalbot.EvalBot()
    elif classname == 'juan.Juandissimo':
        logger.debug("Juandissimo class selected. Initializing.")
        bot = juan.Juandissimo(bot_logger)
    elif classname == 'clippy.Clippy':
        logger.debug("Clippy class selected. Initializing.")
        bot = clippy.Clippy(bot_logger)
    else:
        logger.error("No class found. Closing.")
        exit(1)

    if sys.platform != 'linux' or debug:
        try:
            logger.info("Adding debug cog.")
            bot.add_cog(Debug(bot))
        except commands.ExtensionFailed:
            pass

    logger.info("Calling run method.")
    try:
        bot.run(authentication.tokens[name])
    finally:
        try:
            exit_code = bot._exit_code
        except AttributeError:
            logger.info("Bot's exit code could not be retrieved.")
            exit_code = 0
        logger.info(f"Bot closed with exit code {exit_code}.")
        exit(exit_code)


def main():

    parser = ArgumentParser(description="Start a bot")
    parser.add_argument('bot')
    parser.add_argument('--debug', '-d', action='store_true')

    args = parser.parse_args()

    start(args.bot, args.debug)


if __name__ == "__main__":
    main()
