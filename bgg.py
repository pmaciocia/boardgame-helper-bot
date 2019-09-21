import logging
import discord

from discord.ext import commands
from boardgamegeek import BGGClient

logger = logging.getLogger("boardgame.helper.bgg")


class BGGCog(commands.Cog, name="BGG"):
    def __init__(self, bot):
        self.bot = bot
        self._bgg = BGGClient()

    @staticmethod
    def game_path(game):
        return f"https://boardgamegeek.com/boardgame/{game.id}"

    async def fetch_game(self, name=None, id=None):
        if id:
            return [self._bgg.game(game_id=id)]
        if name:
            return self._bgg.games(name)
        return []

    @commands.command(name='bg', help='Lookup a board game')
    async def lookup(self, ctx: commands.Context, *, message):
        if len(message) == 0:
            return

        user = ctx.message.author
        game_name = message

        logger.info(f"Looking up game '{message}' for user {user.id}")
        await ctx.trigger_typing()

        games = []
        if game_name.isdigit():
            games = await self.fetch_game(id=int(game_name))
        else:
            games = await self.fetch_game(name=game_name)

        if len(games) == 0:
            response = "Hmm... not heard of that one!"
            await ctx.send(response)
        elif len(games) == 1:
            response = f"{user.mention} I found this game with the {'id' if game_name.isdigit() else 'name'} {game_name}!"
            await ctx.send(response)

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

            await ctx.send(embed=embed)
        else:
            response = f"{user.mention} I found {len(games)} games with the name {game_name}!"
            await ctx.send(response)
            embed = discord.Embed(title=f"Games matching '{game_name}'")

            for game in sorted(games, key=lambda g: g.boardgame_rank or float('inf')):
                embed.add_field(name=f"{game.name} ({game.year})",
                                value=BGGCog.game_path(game))

            embed.set_footer(text="Sorted by descending rank")
            await ctx.send(embed=embed)
