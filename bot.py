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


# @bot.command(name='add_game', help='Add a game you will be bringing')
# async def add_game(ctx, *, message):
#     user = ctx.message.author
#     game_name = message

#     await ctx.trigger_typing()
#     games = await fetch_game(game_name)
#     if len(games) == 0:
#         response = f"Thanks <@{user.id}>! Adding game {game_name}!"
#         await ctx.send(response)
#     else:
#         game = games[0]
#         embed = game_embed(game, game.name, f"<@{user.id}> wants to play {game.name}!")
#         await ctx.send(embed=embed)

# @bot.command(name='games', help='List games that are being played')
# async def list_games(ctx):
#     response = f"Adding game"
#     await ctx.send(response)

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
