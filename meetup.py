import logging
import discord
import sys

from discord.ext import commands

logger = logging.getLogger("boardgame.helper.games")

class Meetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._games = {}
    
    @commands.command(name='add_game', help='Add a game you are bringing')
    async def add_game(self, ctx: commands.Context, *, message):
        user = ctx.message.author
        logger.info(f"Add game {message} for user {user.id}")

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
                bgg_game = sorted(bgg_games, key=lambda g: g.boardgame_rank or sys.maxsize)[0]

            game = Game(game_name, user, bgg_game)

            recommend = max((rank.best, rank.player_count) for rank in bgg_game._player_suggestion)[1]
            link = bgg.game_path(bgg_game)
            description = bgg_game.description
            if len(bgg_game.description) > 300:
                description = description[:297] + "..."

            embed = discord.Embed(title=bgg_game.name, url=link, 
                description=f"{user.mention} is bringing {bgg_game.name}!")
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
        user = ctx.message.author
        logger.info(f"Remove game for user {user.id}")

        if not user in self._games:
            response = f"{user.mention}, you are not bringing a game"
            await ctx.send(response)
            return

        game = self._games[user]
        players = ", ".join([p.mention for p in game.players])
        response = f"Sorry {players}, but {user.display_name} is not bringing {game.name} anymore!"

        del self._games[user]
        await ctx.send(response)

    @commands.command(name='list_games', help='List games that people are bringing')
    async def list_games(self, ctx: commands.Context):
        embed = discord.Embed(title="Games being brought")
        for game in self._games.values():
            name = f"{game.name}, brought by {game.owner.display_name}"
            if len(game.players) > 0:
                players = ", ".join(p.display_name for p in game.players)
                value = f"{players} are playing ({len(game.players)+1}/{game.maxplayers})"
            else:
                value = f"No-one has signed up yet! (1/{game.maxplayers})"
            embed.add_field(name=name, value=value)
        
        await ctx.send(embed=embed)
        
    @commands.command(name='list_players', help='List people that want to play your game')
    async def list_players(self, ctx: commands.Context):
        user = ctx.message.author
        logger.info(f"List players for user {user.id}")

        if not user in self._games:
            response = f"{user.mention}, you are not bringing a game"
            await ctx.send(response)
            return
        
        game = self._games[user]
        if len(game.players) > 0:
            players = ", ".join(p.display_name for p in game.players)
            response = f"{user.mention}, here are the people who have signed up to play {game.name}:\n{players}"
        else:
            response = f"{user.mention}, no-one has signed up yet to play {game.name}"

        await ctx.send(response)


    @commands.command(name='join_game', help='Join a game that someone is bringing')
    async def join_game(self, ctx, *, message):
        pass

class Game():
    def __init__(self, name, user, bgg_game=None):
        self.bgg_game = bgg_game
        self.name = bgg_game.name if bgg_game else name
        self.owner = user
        self.maxplayers = bgg_game.max_players if bgg_game else -1
        self.players = []

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