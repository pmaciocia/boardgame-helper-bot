import os
import discord
import sqlite3

from environs import Env

from bgg import BGGCog
from meetup import Meetup

from discord.ext import commands
from boardgamegeek import BGGClient

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("boardgame.helper")

env = Env()
env.read_env()

token = env.str("DISCORD_TOKEN")

def main():
    bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'),)

    async def on_ready():
        logger.info(f'{bot.user} has connected to Discord!')

    bot.add_listener(on_ready)
    bot.add_check(commands.guild_only())
    bot.add_cog(BGGCog(bot))
    bot.add_cog(Meetup(bot))
    bot.run(token)

if __name__ == "__main__":
   main()
