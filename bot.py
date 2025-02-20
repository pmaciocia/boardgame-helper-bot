import os
import discord
import sqlite3

from environs import Env

from meetup import Meetup

from discord.ext import commands
from boardgamegeek import BGGClient

import logging
import pickle

from store.mem import MemoryStore
from store.local import SQLiteStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("boardgame.helper")
logger.setLevel(logging.DEBUG)

env = Env()
env.read_env()

token = env.str("DISCORD_TOKEN")


def main():
    
    # store = MemoryStore()
    # try:
    #     with open('store.pickle', 'rb') as f:
    #         # Pickle the 'data' dictionary using the highest protocol available.
    #         store = pickle.load(f)
    # except:
    #     logger.error('Failed to load store', exc_info=True)
    
    store = SQLiteStore()

    bot = commands.Bot(intents=discord.Intents.default())
    async def on_ready():
        logger.info('%s has connected to Discord!', bot.user)

    bot.add_listener(on_ready)
    bot.add_check(commands.guild_only())
    bot.load_extension("bgg")
    meetup = Meetup(bot, store, BGGClient(timeout=10))
    bot.add_listener(meetup.on_ready, "on_ready")
    bot.add_cog(meetup)
    bot.run(token)

    # try:
    #     with open('store.pickle', 'wb') as f:
    #         # Pickle the 'data' dictionary using the highest protocol available.
    #         pickle.dump(store, f, pickle.HIGHEST_PROTOCOL)
    # except:
    #     logger.error('Failed to save store', exc_info=True)


if __name__ == "__main__":
    main()
