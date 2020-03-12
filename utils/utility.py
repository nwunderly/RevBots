import discord
from discord.ext import commands

import logging
import sys
import datetime

from authentication.authentication import linux_username


if sys.platform == 'linux':
    home_dir = f'/home/{linux_username}'
else:
    home_dir = ''


def list_by_category(guild):
    channels = []
    for category, category_channels in guild.by_category():
        if category is not None:
            channels.append(category)
        for channel in category_channels:
            channels.append(channel)
    return channels


def setup_logger(name):
    logger = logging.getLogger(name)
    d = datetime.datetime.now()
    time = f"{d.month}-{d.day}_{d.hour}h{d.minute}m"

    if sys.platform == 'linux':
        filename = home_dir + '/logs/{}/{}.log'
        level = logging.DEBUG  # INFO
    else:
        filename = '../RevBots/logs/{}/{}.log'
        level = logging.DEBUG

    file_handler = logging.FileHandler(filename.format(name, time))
    # file_handler.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stdout)
    # stream_handler.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.setLevel(level)
    return logger


def module_logger(name, extension, level=logging.DEBUG, stream=True, file=True):
    logger = logging.getLogger(extension)  # logger name is cog name
    d = datetime.datetime.now()
    time = f"{d.month}-{d.day}_{d.hour}h{d.minute}m"

    if sys.platform == 'linux':
        filename = home_dir + '/logs/{}/{}.log'
    else:
        filename = '../RevBots/logs/{}/{}.log'
    # uses name to log in the same file as bot logger
    file_handler = logging.FileHandler(filename.format(name, time))
    # file_handler.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stdout)
    # stream_handler.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    if file:
        logger.addHandler(file_handler)
    if stream:
        logger.addHandler(stream_handler)
    logger.setLevel(level)
    return logger


def stream_logger(name):
    logger = logging.getLogger(name)
    stream_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger
