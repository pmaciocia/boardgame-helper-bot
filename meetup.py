import logging
import discord
from collections import defaultdict
from typing import List

import sys

from discord.ext import commands
from discord.commands import SlashCommandGroup

from store import *


logger = logging.getLogger("boardgame.helper.games")


class Meetup(commands.Cog):
    def __init__(self, bot: discord.Bot, store: Store):
        self.bot = bot
        self.store = store

    meetup = SlashCommandGroup("meetup", "meetup group")
    games = meetup.create_subgroup("games", "Manage games")
    manage = meetup.create_subgroup(
        "manage", "Manage games", checks=commands.is_owner().predicate)

    @manage.command(name='reset', help='Reset the games')
    async def reset(self, ctx):
        logger.info(f"Resetting...")
        await ctx.message.add_reaction('👌')

    @games.command(name='add', help='Add a game you are bringing')
    async def add_game(self, ctx: discord.ApplicationContext, game_name: str):
        user = ctx.author
        guild = ctx.guild

        try:
            event = self.store.get_event_for_guild_id(guild_id=guild.id)
            if event is None:
                event = self.store.add_event(guild_id=guild.id, event_id="test")

            logger.info(
                f"Add game {game_name} for user {user.id}, guild {guild.id}, event {event.id}")

            owner = Player(user.id, user.display_name, user.mention)

            bgg = self.bot.get_cog("BGG")
            if bgg:
                await ctx.defer()
                bgg_games = bgg.fetch_game(game_name)
                if len(bgg_games) > 0:
                    bgg_game = sorted(
                        bgg_games, key=lambda g: g.boardgame_rank or sys.maxsize)[0]
                else:
                    await ctx.respond(content="couldn't find that game")
                    return

                game = Game(game_name, bgg_game)
                embed = game_to_embed(game, owner)
                await ctx.respond(embed=embed)
            else:
                game = Game(game_name)
                response = f"{user.mention} is bringing {game.name}"
                await ctx.respond(response)

            self.store.add_table(event, owner, game)
        except Exception as e:
            logger.error("Failed to add game", exc_info=True)
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='remove', help='Remove a game you were bringing')
    async def remove_game(self, ctx: discord.ApplicationContext):
        user = ctx.author
        guild = ctx.guild
        logger.info(f"Remove game for user {user.id}, guild {guild.id}")

        try:
            event = self.store.get_event_for_guild_id(guild_id=guild.id)
            if event is None:
                response = f"No upcoming events for this server"
                await ctx.respond(response)
                return
            
            table = event.tables.get(user.id)
            if table is None:
                response = f"You are not bringing a game"
                await ctx.respond(response)
                return
            
            game = table.game
            players = table.players.values()
            self.store.remove_table(table)

            players = ", ".join([p.mention for p in players])
            response = f"Sorry {players}, but {user.display_name} is not bringing {game.name} anymore!"
            await ctx.respond(response)
        except Exception as e:
            logger.error("Failed to remove game", exc_info=True)
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='list', help='List games that people are bringing')
    async def list_games(self, ctx):
        user = ctx.author
        guild = ctx.guild
        
        logger.info(f"List games for user {user.id}, guild {guild.id}")

        try:
            event = self.store.get_event_for_guild_id(guild_id=guild.id)
            if event is None:
                response = f"No upcoming events for this server"
                await ctx.respond(response)
                return

            if len(event.tables) == 0:
                response = f"No games yet for the next event"
                await ctx.respond(response)
                return

            embed = discord.Embed(title="Games being brought")
            for table in event.tables.values():
                game = table.game
                owner = table.owner
                name = f"{game.name}, brought by {owner.display_name}"
                if len(table.players) > 0:
                    players = ", ".join([p.display_name for p in table.players.values()])
                    value = f"{players} {"is" if len(players) == 1 else "are"} playing ({len(table.players)}/{game.maxplayers})"
                else:
                    value = f"No-one has signed up yet! (1/{game.maxplayers})"
                embed.add_field(name=name, value=value, inline=False)

            await ctx.respond(embed=embed)
        except Exception as e:
            logger.error("Failed to list games", exc_info=True)
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='players', help='List people that want to play your game')
    async def list_players(self, ctx):
        user = ctx.author
        guild = ctx.guild
        logger.info(f"List players for user {user.id}, guild {guild.id}")

        try:
            event = self.store.get_event_for_guild_id(guild_id=guild.id)
            if event is None:
                response = f"No upcoming events for this server"
                await ctx.respond(response)
                return
            
            player = self.store.get_player(user.id)

            table = event.tables[player]
            if table is None:
                response = f"{user.mention}, you are not bringing any games"
                await ctx.respond(response)
                return

            game = table.game
            embed = discord.Embed(title=f"Players for {user.display_name}'s games")
            if len(game.players) > 0:
                players = ", ".join(game.player_names())
                response = f"Players: {players}"
            else:
                response = f"No-one has signed up yet to play {game.name}"

            embed.add_field(name=game.name, value=response, inline=False)
            await ctx.respond(embed=embed)
        except Exception as e:
            logger.error(e)
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='join', help='Join a game that someone is bringing')
    async def join_game(self, ctx: discord.ApplicationContext):
        user = ctx.author
        guild = ctx.guild
        
        try:
            event = self.store.get_event_for_guild_id(guild_id=guild.id)
            if event is None:
                response = f"No upcoming events for this server"
                await ctx.respond(response)
                return
                    
            tables = event.tables.values()
            if len(tables) == 0:
                await ctx.respond(f"{user.mention}, No-one is bringing any games yet!")
                return

            await ctx.respond("Pick a game", view=GameListView(self.bot, tables))
        except Exception as e:
            logger.error("Failed to join game", exc_info=True)
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)


class GameList(discord.ui.Select):
    def __init__(self, bot_: discord.Bot, tables):
        self.bot = bot_
        self.tables = list(tables)
        
        options = [
            discord.SelectOption(label=table.game.name, description=table.game.description[:100], value=str(idx), ) for idx, table in enumerate(self.tables)
        ]

        super().__init__(
            placeholder="Choose what game to play...",
            min_values=1,
            max_values=1,
            options=options,   
        )

    # the function called when the user is done selecting options
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            select = int(self.values[0])
            await interaction.followup.edit_message(interaction.message.id, content=f"You chose {self.tables[select].game.name}", view=None)
        except:
            logger.error("Failed to select game", exc_info=True)
            await interaction.followup.edit_message(interaction.message.id, content="Something went wrong", view=None)
            
            


class GameListView(discord.ui.View):
    def __init__(self, bot_: discord.Bot, games: list):
        self.bot = bot_
        # Adds the dropdown to our View object
        super().__init__(GameList(self.bot, games), timeout=30)
       

def game_to_embed(game, player):
    description = game.description
    if len(game.description) > 300:
        description = description[:297] + "..."

    embed = discord.Embed(title=game.name, url=game.link, description=f"{player.mention} is bringing {game.name}!")
    embed.add_field(name="Players", value=f"{game.minplayers}-{game.maxplayers}", inline=True)
    embed.add_field(name="Best", value=game.recommended_players, inline=True)
    embed.add_field(name="Description", value=description)
    embed.set_thumbnail(url=game.thumbnail)
    return embed