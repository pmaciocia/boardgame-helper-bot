import logging
import discord

from discord.ext import commands

logger = logging.getLogger("boardgame.helper.games")

class Meetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._games = {}
    
    @commands.command(name='add_game', help='Add a game you are bringing')
    async def add_game(self, ctx: commands.Context, *, message):
        user = ctx.message.author

        if user in self._games:
            game = self._games[user]
            response = f"{user.mention()}, you are already bringing {game.name}"
            await ctx.send(response)
            return

        game_name = message

        bgg = self.bot.get_cog("BGGCog")
        if bgg:
            await ctx.trigger_typing()
            bgg_games = await bgg.fetch_game(game_name)
            if len(bgg_games) > 0:
                bgg_game = sorted(bgg_games, key=lambda g: g.boardgame_rank)[0]

            game = Game(game_name, user, bgg_game)

            recommend = max((rank.best, rank.player_count) for rank in bgg_game._player_suggestion)[1]
            link = bgg.game_path(bgg_game)
            description = bgg_game.description
            if len(bgg_game.description) > 300:
                description = description[:297] + "..."

            embed = discord.Embed(title=bgg_game.name, url=link, description=f"{user.mention} is bringing {bgg_game.name}!")
            embed.add_field(
                name="Players", value=f"{bgg_game.min_players}-{bgg_game.max_players}", inline=True)
            embed.add_field(name="Best", value=recommend, inline=True)
            embed.add_field(name="Description", value=description)
            embed.set_thumbnail(url=bgg_game.thumbnail)

            await ctx.send(embed=embed)
        else:
            game = Game(game_name, user)

            response = f"{user.mention} is bringing {game.name}"
            await ctx.send(response)

        self._games[user] = game

    @commands.command(name='remove_game', help='Remove a game you were bringing')
    async def remove_game(self, ctx: commands.Context):
        pass

    @commands.command(name='list_games', help='List games that people are bringing')
    async def list_games(self, ctx: commands.Context):
        embed = discord.Embed(title="Games being brought")
        for game in self._games.values():
            players = ", ".join([p.display_name for p in game.players])
            embed.add_field(name=game.name, value=f"{players} are playing ({len(game.players)}/{game.maxplayers})")
        
        await ctx.send(embed=embed)
        


    @commands.command(name='list_players', help='List people that want to play your game')
    async def list_players(self, ctx: commands.Context):
        pass

class Game():
    def __init__(self, name, user, bgg_game=None):
        self.bgg_game = bgg_game
        self.name = bgg_game.name if bgg_game else name
        self.owner = user
        self.maxplayers = bgg_game.max_players if bgg_game else -1
        self.players = [user]

    def add_player(self, user):
        if len(self.players) + 1 > self.maxplayers:
            raise Exception("Too many players")

        if not user in self.players:
            self.players.append(user)
            return True
        else:
            return False

    def list_players(self):
        return self.players

    def remove_player(self, user):
        self.players.remove(user)