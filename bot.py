import os
import discord
import sqlite3

from bgg import BGGCog
from meetup import Meetup

from discord.ext import commands
from boardgamegeek import BGGClient

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("boardgame.helper")

token = "NjIzODc1NDUwMDA2OTI5NDE5.XYI4Zg.JAOi5EtyGT_YufPf2urK915e26Y"

def main():
    bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'),)

    async def on_ready():
        logger.info(f'{bot.user} has connected to Discord!')

    bot.add_listener(on_ready)
    bot.add_cog(BGGCog(bot))
    bot.add_cog(Meetup(bot))
    bot.run(token)

if __name__ == "__main__":
   main()
