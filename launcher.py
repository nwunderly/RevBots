
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


def start(name, debug):
    if name == "marvin":
        start_marvin(debug)
    else:
        start_bot(name, debug)


def start_marvin(debug=False):
    logger = setup_logger("marvin")
    marv = marvin.Marvin(logger)
    try:
        marv.run(debug=debug)
    finally:
        marv.logger.info("Bot closed.")
        exit(0)


def start_bot(name, debug=False):
    bot_logger = setup_logger(name)
    logger = module_logger(name, "launcher")
    module_logger(name, 'discord', logging.INFO)

    logger.info(f"Starting {name}.")

    with open(f"{HOME_DIR}/configs/marvin.yaml") as f:
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
        bot = revbot.RevBot(command_prefix='__', name=name, logger=bot_logger)
    elif classname == 'bulbe.Bulbe':
        bot = bulbe.Bulbe(name=name, logger=bot_logger)
    elif classname == 'evalbot.EvalBot':
        bot = evalbot.EvalBot()
    elif classname == 'juan.Juandissimo':
        bot = juan.Juandissimo(bot_logger)
    elif classname == 'clippy.Clippy':
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

    # todo remove this when admin.py is working
    try:
        logger.info("Adding eval cog.")
        bot.add_cog(evalbot.EvalCog(bot))
    except commands.ExtensionFailed:
        pass

    logger.info("Calling run method.")
    try:
        bot.run(authentication.tokens[name])
    finally:
        logger.info("Bot closed.")
        exit(0)


def main():

    parser = ArgumentParser(description="Start a bot")
    parser.add_argument('bot')
    parser.add_argument('--debug', '-d', action='store_true')

    args = parser.parse_args()

    start(args.bot, args.debug)


if __name__ == "__main__":
    main()
