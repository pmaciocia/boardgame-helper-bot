import os
import discord
import sqlite3

from environs import Env

from bgg import BGGCog
from meetup import Meetup

from discord.ext import commands

import logging

from store import MemoryStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("boardgame.helper")

env = Env()
env.read_env()

token = env.str("DISCORD_TOKEN")


def main():
    store = MemoryStore()

    bot = commands.Bot(intents=discord.Intents.default())
    async def on_ready():
        logger.info(f'{bot.user} has connected to Discord!')

    bot.add_listener(on_ready)
    bot.add_check(commands.guild_only())
    bot.load_extension("bgg")
    bot.add_cog(Meetup(bot, store))
    bot.run(token)


if __name__ == "__main__":
    main()
