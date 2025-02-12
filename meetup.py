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
                event = self.store.add_event(
                    guild_id=guild.id, event_id="test")

            logger.info(
                f"Add game {game_name} for user {user.id}, guild {guild.id}, event {event.id}")

            owner = Player(user.id, user.display_name, user.mention)

            bgg = self.bot.get_cog("BGG")
            embed = None
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
            else:
                game = Game(game_name)

            table = self.store.add_table(event, owner, game)
            await ctx.respond(embed=GameEmbed(table))
            
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
                    players = ", ".join(
                        [p.display_name for p in table.players.values()])
                    value = f"{players} {"is" if len(players) == 1 else "are"} playing ({len(table.players)}/{game.maxplayers})"
                else:
                    value = f"No-one has signed up yet! (1/{game.maxplayers})"
                embed.add_field(name=name, value=value, inline=False)

            await ctx.respond(embed=embed, ephemeral=True)
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
                await ctx.respond(response, ephemeral=True)
                return

            player = self.store.get_player(user.id)

            table = event.tables[player.id]
            if table is None:
                response = f"{user.mention}, you are not bringing any games"
                await ctx.respond(response, ephemeral=True)
                return

            await ctx.respond(embed=PlayerListEmbed(table), ephemeral=True)
        except Exception as e:
            logger.error("Failed to list players", exc_info=True)
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='join', help='Join a game that someone is bringing')
    async def join_game(self, ctx: discord.ApplicationContext):
        user = ctx.author
        guild = ctx.guild

        try:
            event = self.store.get_event_for_guild_id(guild_id=guild.id)
            if event is None:
                response = f"No upcoming events for this server"
                await ctx.respond(response, ephemeral=True)
                return

            tables = list(event.tables.values())
            if len(tables) == 0:
                await ctx.respond(f"{user.mention}, No-one is bringing any games yet!", ephemeral=True)
                return

            embed = GameEmbed(tables[0])
            view = GameListView(tables=tables)
            await ctx.respond("Pick a game", embed=embed, view=view, ephemeral=True)

            await view.wait()
            logger.info("view.await() - choice=%s", view.choice)

            if view.choice is not None:
                player = self.store.get_player(user.id) or Player(user.id, user.display_name, user.mention)
                table = tables[view.choice]
                logging.info("user: %s/%s selected game %s", user.id, user.display_name,  table.game.name)

                self.store.join_table(player=player, table=table)


        except Exception as e:
            logger.error("Failed to join game", exc_info=True)
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)


class GameListView(discord.ui.View):
    def __init__(self, tables: list):
        self.tables = tables
        self.index = 0
        self.choice = None

        # Adds the dropdown to our View object
        super().__init__(timeout=30, disable_on_timeout=True)

        self.children[0].disabled = True
        self.children[1].disabled = len(tables) == 1

    async def on_timeout(self):
        logging.info("timeout GameListView")
        self.clear_items()
        interaction = self.parent
        if interaction:
            await interaction.message.edit(content="Timed out", view=None)

    async def edit_page(self, interaction: discord.Interaction):
        logging.info("index: %s - tables: %d", self.index, len(self.tables))
        table = self.tables[self.index]
        l, r = self.children[0:2]
        l.disabled = self.index == 0
        r.disabled = self.index == len(self.tables)-1

        e = GameEmbed(table)
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.blurple)
    async def previous(self, button: discord.Button, interaction: discord.Interaction ):
        logging.info("LEFT BUTTON:- index: %s - tables: %d", self.index, len(self.tables))
        self.index = max(self.index-1, 0)
        await self.edit_page(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.blurple)
    async def next(self, button: discord.Button, interaction: discord.Interaction):
        logging.info("RIGHT BUTTON:- index: %s - tables: %d", self.index, len(self.tables))
        self.index = min(self.index+1, len(self.tables)-1)
        await self.edit_page(interaction)

    @discord.ui.button(emoji="✅", style=discord.ButtonStyle.blurple)
    async def join(self, button: discord.Button, interaction: discord.Interaction):
        logging.info("JOIN BUTTON:- index: %s - tables: %d", self.index, len(self.tables))
        self.choice = self.index
        await interaction.response.send_message(
            content=f"You chose {self.tables[self.index].game.name}", ephemeral=True)
        
        self.clear_items()
        self.stop()

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.blurple)
    async def cancel(self, button: discord.Button, interaction: discord.Interaction):
        logging.info("CANCEL BUTTON:- index: %s - tables: %d", self.index, len(self.tables))
        await interaction.response.send_message('Cancelled', delete_after=1, ephemeral=True)
        self.clear_items()
        self.stop()

class GameEmbed(discord.Embed):
    def __init__(self, table: Table):
        owner = table.owner
        game = table.game
        super().__init__(title=game.name, url=game.link,
                         description=f"{owner.mention} is bringing {game.name}")

        description = game.description
        if len(game.description) > 300:
            description = description[:297] + "..."

        self.add_field(
            name="Players", value=f"{game.minplayers}-{game.maxplayers}", inline=True)
        self.add_field(
            name="Best", value=game.recommended_players, inline=True)
        self.add_field(name="Description", value=description)
        self.set_thumbnail(url=game.thumbnail)

        if len(table.players) > 0:
            self.add_field(name="Currently signed up to play:", 
                value=(", ".join(p.display_name for p in table.players.values())))
            
class PlayerListEmbed(discord.Embed):
    def __init__(self, table: Table):
        owner = table.owner
        game = table.game
        super().__init__(title=game.name, url=game.link,
                         description=f"{owner.mention} is bringing {game.name}")

        title=f"Players for {owner.display_name}'s games"
        if len(table.players) > 0:
            players = ", ".join(
                p.display_name for p in table.players.values())
            response = f"Players: {players}"
        else:
            response = f"No-one has signed up yet to play {game.name}"

        self.add_field(name=game.name, value=response, inline=False)