import logging
from boardgamegeek import BGGClient, BGGRestrictSearchResultsTo

import discord
from discord.ext import commands

from functools import lru_cache

logger = logging.getLogger("boardgame.helper.bgg")


class BGGCog(commands.Cog, name="BGG"):
    
    def __init__(self, bot):
        self.bot = bot
        self._bgg = BGGClient()

    @staticmethod
    def game_path(game):
        return f"https://boardgamegeek.com/boardgame/{game.id}"

    @lru_cache(maxsize=128)
    def fetch_game(self, name=None, id=None):
        if id:
            return [self._bgg.game(game_id=id)]
        if name:
            games = self._bgg.search(
                 name,search_type=[BGGRestrictSearchResultsTo.BOARD_GAME, BGGRestrictSearchResultsTo.BOARD_GAME_EXPANSION]
                 )
            return [self._bgg.game(g.id) for g in games]

    # @commands.command(name='bg', help='Lookup a board game')
    @discord.slash_command()
    async def lookup(self, ctx: discord.ApplicationContext, game_name: str):
        user = ctx.author

        logger.info(f"Looking up game '{game_name}' for user {user.id}")
        await ctx.defer()

        games = []
        if game_name.isdigit():
            games = self.fetch_game(id=int(game_name))
        else:
            games = self.fetch_game(name=game_name)

        if len(games) == 0:
            response = "Hmm... not heard of that one!"
            await ctx.respond(response)
        elif len(games) == 1:
            response = f"{user.mention} I found this game with the {'id' if game_name.isdigit() else 'name'} {game_name}!"
            await ctx.respond(response)

            game = games[0]
            recommend = max((rank.best, rank.player_count)
                            for rank in game._player_suggestion)[1]
            link = BGGCog.game_path(game)
            description = game.description
            if len(game.description) > 300:
                description = description[:297] + "..."

            embed = discord.Embed(title=game.name, url=link)
            embed.add_field(
                name="Players", value=f"{game.min_players}-{game.max_players}", inline=True)
            embed.add_field(name="Best", value=recommend, inline=True)
            embed.add_field(name="Description", value=description)
            embed.set_thumbnail(url=game.thumbnail)

            await ctx.respond(embed=embed)
        else:
            response = f"{user.mention} I found {len(games)} games with the name {game_name}!"
            await ctx.respond(response)
            embed = discord.Embed(title=f"Games matching '{game_name}'")

            for game in sorted(games, key=lambda g: g.boardgame_rank or float('inf')):
                embed.add_field(name=f"{game.name} ({game.year})",
                                value=BGGCog.game_path(game))

            embed.set_footer(text="Sorted by descending rank")
            await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(BGGCog(bot))