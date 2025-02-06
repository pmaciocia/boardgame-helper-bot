import logging
import discord
from collections import defaultdict
from typing import List

import sys

from discord.ext import commands
from discord.commands import SlashCommandGroup


logger = logging.getLogger("boardgame.helper.games")


class Meetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._games = defaultdict(lambda: {})
        
    meetup = SlashCommandGroup("meetup", "meetup group")
    games = meetup.create_subgroup("games", "Manage games")
    manage = meetup.create_subgroup("manage", "Manage games", checks = commands.is_owner().predicate)
    
    @manage.command(name='reset', help='Reset the games')
    async def reset(self, ctx):
        logger.info(f"Resetting...")
        self._games.clear()
        await ctx.message.add_reaction('👌')


    @games.command(name='add', help='Add a game you are bringing')
    async def add_game(self, ctx: discord.ApplicationContext, game_name: str):
        user = ctx.author
        logger.info(f"Add game {game_name} for user {user.id}")

        bgg = self.bot.get_cog("BGG")
        if bgg:
            await ctx.defer()
            bgg_games = bgg.fetch_game(game_name)
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

            await ctx.respond(embed=embed)
        else:
            game = Game(game_name, user)

            response = f"{user.mention} is bringing {game.name}"
            await ctx.respond(response)

        self._games[user][game.name.lower()] = game

    @games.command(name='remove', help='Remove a game you were bringing')
    async def remove_game(self, ctx: discord.ApplicationContext, game_name):
        user = ctx.author
        logger.info(f"Remove game {game_name} for user {user.id}")

        if not user in self._games:
            response = f"{user.mention}, you are not bringing any games"
            await ctx.respond(response)
            return

        games = self._games[user]
        if not game_name in games:
            response = f"{user.mention}, you are not bringing any games named {game_name}"
            await ctx.respond(response)
            return

        game = games[game_name]
        players = ", ".join([p.mention for p in game.players])
        response = f"Sorry {players}, but {user.display_name} is not bringing {game.name} anymore!"

        del self._games[user][game_name]
        await ctx.respond(response)

    @games.command(name='list', help='List games that people are bringing')
    async def list_games(self, ctx):
        user = ctx.author

        games = self._games.values()
        if len(games) == 0:
            await ctx.respond(f"{user.mention}, No-one is bringing any games yet!")
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

        await ctx.respond(embed=embed)

    @games.command(name='players', help='List people that want to play your game')
    async def list_players(self, ctx):
        user = ctx.author
        logger.info(f"List players for user {user.id}")

        if not user in self._games:
            response = f"{user.mention}, you are not bringing any games"
            await ctx.respond(response)
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

        await ctx.respond(embed=embed)

    @games.command(name='join', help='Join a game that someone is bringing')
    async def join_game(self, ctx: discord.ApplicationContext):
        user = ctx.author
        games = [ game for games in self._games.values() for game in games.keys() ]
        if len(games) == 0:
            await ctx.respond(f"{user.mention}, No-one is bringing any games yet!")
            return
        
        await ctx.respond("Pick a game", view=GameListView(self.bot, games))
        

class GameList(discord.ui.Select):
    def __init__(self, bot_: discord.Bot, games: list):
        self.bot = bot_
        options = [
            discord.SelectOption(label=game, value=game) for game in games
        ]
        
        super().__init__(
            placeholder="Choose what game to play...",
            min_values=1,
            max_values=1,
            options=options,
        )
   
    async def callback(self, interaction: discord.Interaction): # the function called when the user is done selecting options
        await interaction.response.send_message(
            f"You chose {self.values[0]}"
        )
        
class GameListView(discord.ui.View):
    def __init__(self, bot_: discord.Bot, games: list):
        self.bot = bot_
        # Adds the dropdown to our View object
        super().__init__(GameList(self.bot, games))

        # Initializing the view and adding the dropdown can actually be done in a one-liner if preferred:
        # super().__init__(Dropdown(self.bot))

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
