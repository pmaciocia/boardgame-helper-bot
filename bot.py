import os
import discord
from discord.ext import commands

from boardgamegeek import BGGClient

token = "NjIzODc1NDUwMDA2OTI5NDE5.XYI4Zg.JAOi5EtyGT_YufPf2urK915e26Y"

bot = commands.Bot(command_prefix='!')

bgg = BGGClient()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')


@bot.command(name='add_game', help='Add a game you will be bringing')
async def add_game(ctx, *, message):
    user = ctx.message.author
    game_name = message

    games = bgg.games(game_name)     
    if len(games) == 0:
        response = f"Thanks <@{user.id}>! Adding game {game_name}!"
        await ctx.send(response)
    else:
        game = games[0]
        
        name = game.name
        min_player = game.min_players
        max_player = game.max_players
        recommend = max((rank.best, rank.player_count) for rank in game._player_suggestion)[1]
        link = f"https://boardgamegeek.com/boardgame/{game.id}"
        weight = game.rating_average_weight

        embed = discord.Embed(title=name,
                       url=link,
                       description=f"<@{user.id}> wants to play {game.name}!")

        embed.add_field(name="Players", value=f"{min_player}-{max_player}", inline=True)
        embed.add_field(name="Best", value=recommend, inline=True)

        description=game.description
        if len(game.description) > 300:
            description = description[:297] + "..."

        embed.add_field(name="Description", value=description)
        embed.set_thumbnail(url=game.thumbnail)

        await ctx.send(embed=embed)

@bot.command(name='games', help='List games that are being played')
async def list_games(ctx):
    response = f"Adding game"
    await ctx.send(response)

bot.run(token)
