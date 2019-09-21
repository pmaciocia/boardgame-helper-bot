import logging
import discord
from collections import defaultdict

import sys

from discord.ext import commands

logger = logging.getLogger("boardgame.helper.games")


class Meetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._games = defaultdict(lambda: {})

    @commands.command(name='reset', hidden=True)
    @commands.is_owner()
    async def reset(self, ctx):
        logger.info(f"Resetting...")
        self._games.clear()
        await ctx.message.add_reaction('👌')

    @commands.command(name='add_game', help='Add a game you are bringing')
    async def add_game(self, ctx: commands.Context, *, message):
        user = ctx.message.author
        logger.info(f"Add game {message} for user {user.id}")

        game_name = message

        bgg = self.bot.get_cog("BGG")
        if bgg:
            await ctx.trigger_typing()
            bgg_games = await bgg.fetch_game(game_name)
            if len(bgg_games) > 0:
                bgg_game = sorted(
                    bgg_games, key=lambda g: g.boardgame_rank or sys.maxsize)[0]

            game = Game(game_name, user, bgg_game)

            recommend = max((rank.best, rank.player_count)
                            for rank in bgg_game._player_suggestion)[1]
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

        self._games[user][game.name.lower()] = game

    @commands.command(name='remove_game', help='Remove a game you were bringing')
    async def remove_game(self, ctx, *, message):
        user = ctx.message.author
        logger.info(f"Remove game {message} for user {user.id}")

        if not user in self._games:
            response = f"{user.mention}, you are not bringing any games"
            await ctx.send(response)
            return

        game_name = message.lower()
        games = self._games[user]

        if not game_name in games:
            response = f"{user.mention}, you are not bringing any games named {game_name}"
            await ctx.send(response)
            return

        game = games[game_name]
        players = ", ".join([p.mention for p in game.players])
        response = f"Sorry {players}, but {user.display_name} is not bringing {game.name} anymore!"

        del self._games[user][game_name]
        await ctx.send(response)

    @commands.command(name='list_games', help='List games that people are bringing')
    async def list_games(self, ctx):
        user = ctx.message.author

        games = self._games.values()
        if len(games) == 0:
            await ctx.send(f"{user.mention}, No-one is bringing any games yet!")
            return

        embed = discord.Embed(title="Games being brought")
        for game in [g for gs in list(games) for g in gs.values()]:
            name = f"{game.name}, brought by {game.owner.display_name}"
            if len(game.players) > 0:
                players = players = ", ".join(game.player_names())
                value = f"{players} are playing ({len(game.players)+1}/{game.maxplayers})"
            else:
                value = f"No-one has signed up yet! (1/{game.maxplayers})"
            embed.add_field(name=name, value=value, inline=False)

        await ctx.send(embed=embed)

    @commands.command(name='list_players', help='List people that want to play your game')
    async def list_players(self, ctx):
        user = ctx.message.author
        logger.info(f"List players for user {user.id}")

        if not user in self._games:
            response = f"{user.mention}, you are not bringing any games"
            await ctx.send(response)
            return

        games = self._games[user]
        embed = discord.Embed(title=f"Players for {user.display_name}'s games")
        for game in games.values():
            if len(game.players) > 0:
                players = ", ".join(game.player_names())
                response = f"Players: {players}"
            else:
                response = f"No-one has signed up yet to play {game.name}"

            embed.add_field(name=game.name, value=response, inline=False)

        await ctx.send(embed=embed)

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
        if len(self.players) + 2 > self.maxplayers:
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

    def player_names(self):
        return [p.display_name for p in self.players]
