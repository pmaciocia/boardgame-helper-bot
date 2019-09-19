import os
import discord

from discord.ext import commands
from boardgamegeek import BGGClient

import logging

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("boardgame.helper")

token = "NjIzODc1NDUwMDA2OTI5NDE5.XYI4Zg.JAOi5EtyGT_YufPf2urK915e26Y"

bgg = BGGClient()

bot = commands.Bot(command_prefix='!')


@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')


@bot.command(name='bg', help='Lookup a board game')
async def lookup(ctx: commands.Context, *, message):
    if len(message) == 0:
        return

    user = ctx.message.author
    game_name = message

    logger.info(f"Looking up game '{message}' for user {user.id}")
    await ctx.trigger_typing()

    games = []
    if game_name.isdigit():
        games = await fetch_game(id=int(game_name))
    else:
        games = await fetch_game(name=game_name)

    if len(games) == 0:
        response = f"Hmm... not heard of that one!"
        await ctx.send(response)
    elif len(games) == 1:
        response = f"<@{user.id}> I found this game with the name {game_name}!"
        await ctx.send(response)

        embed = game_embed(games[0], games[0].name, "")
        await ctx.send(embed=embed)
    else:
        response = f"<@{user.id}> I found {len(games)} games with the name {game_name}!"
        await ctx.send(response)
        embed = discord.Embed(title=f"Games matching '{game_name}'")

        for game in sorted(games, key=lambda g: g.boardgame_rank or float('inf')):
            embed.add_field(name=f"{game.name} ({game.year})",
                            value=f"https://boardgamegeek.com/boardgame/{game.id}")

        await ctx.send(embed=embed)


def game_embed(game, title, desc):
    recommend = max((rank.best, rank.player_count)
                    for rank in game._player_suggestion)[1]
    link = f"https://boardgamegeek.com/boardgame/{game.id}"
    description = game.description
    if len(game.description) > 300:
        description = description[:297] + "..."

    embed = discord.Embed(title=game.name, url=link, description=desc)
    embed.add_field(
        name="Players", value=f"{game.min_players}-{game.max_players}", inline=True)
    embed.add_field(name="Best", value=recommend, inline=True)
    embed.add_field(name="Description", value=description)
    embed.set_thumbnail(url=game.thumbnail)
    return embed


async def fetch_game(name=None, id=None):
    if id:
        return [bgg.game(game_id=id)]
    if name:
        return bgg.games(name)
    return []

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

bot.run(token)
