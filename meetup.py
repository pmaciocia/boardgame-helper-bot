import logging
import discord

from discord import client
from discord.ext import commands
from discord.commands import SlashCommandGroup

from store import *
from embeds import *
from views import *
from views import GameListView


logger = logging.getLogger("boardgame.helper.games")

signup_channel = 1339272062946246696


class Meetup(commands.Cog):
    def __init__(self, bot: discord.Bot, store: Store):
        self.bot = bot
        self.store = store

    meetup = SlashCommandGroup("meetup", "meetup group")
    games = meetup.create_subgroup("games", "Manage games")
    manage = meetup.create_subgroup(
        "manage", "Manage games", checks=commands.is_owner().predicate)

    async def on_ready(self):
        logger.info("Setting up events")
        for event in self.store.get_events():
            for table in list(event.tables.values()):
                message = table.message
                logger.info("Add view for table %s - message %d",
                            table.id, message)
                self.bot.add_view(GameJoinView(
                    table, self.store), message_id=message)

    @manage.command(name='reset', help='Reset the games')
    async def reset(self, ctx: discord.ApplicationContext):
        self.store.reset()

    @games.command(name='add', help='Add a game you are bringing')
    async def add_game(self, ctx: discord.ApplicationContext, game_name: str):
        user = ctx.author
        guild = ctx.guild

        try:
            event = self.store.get_event_for_guild_id(guild_id=guild.id)
            if event is None:
                event = self.store.add_event(
                    guild_id=guild.id, event_id="test", channel_id=signup_channel)

            logger.info(
                f"Add game {game_name} for user {user.id}, guild {guild.id}, event {event.id}")

            owner = Player(user.id, user.display_name, user.mention)

            bgg = self.bot.get_cog("BGG")
            await ctx.defer(ephemeral=True)
            if bgg:
                bgg_games = bgg.fetch_game(name=game_name)
                game = None

                if len(bgg_games) == 0:
                    await ctx.respond(content=f"Couldn't find game '{game_name}'")
                    return

                if len(bgg_games) <= 5:
                    game = Game(game_name, bgg_games[0])
                else:
                    view = GameChooseView(game_name, bgg_games)
                    await ctx.respond(
                        content=f"Found {len(bgg_games)} games with the name '{game_name}'",
                        embed=GamesEmbed(game_name, bgg_games[:5]),
                        view=view,
                    )

                    timeout = await view.wait()
                    if timeout or view.choice is None:
                        view.clear_items()
                        return
                    
                    game = Game(game_name, view.choice)
            else:
                game = Game(game_name)

            table = self.store.add_table(event, owner, game)
            embed = GameEmbed(table)

            await ctx.respond(embed=embed)

            channel = self.bot.get_channel(signup_channel)
            table_message = await channel.send(
                content="Click to join",
                embed=GameEmbed(table, list_players=True),
                view=GameJoinView(table, self.store)
            )
            self.store.add_table_message(table, table_message.id)

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
            logger.debug("Found event %s in guild %s", event.id, guild.id)

            table = event.tables.get(user.id)
            if table is None:
                response = f"You are not bringing a game"
                await ctx.respond(response)
                return
            logger.debug("Found table %s in guild %s", table.id, guild.id)

            game = table.game
            players = table.players.values()
            self.store.remove_table(table)

            players = ", ".join([p.mention for p in players])
            response = f"Sorry {players}, but {user.display_name} is not bringing [{game.name}]<{game.link}> anymore!"
            msg = await ctx.respond(response)

            if not table.message:
                return

            msg = table.message
            logger.debug("Found message %d for table %s", msg, table.id)
            msg = self.bot.get_message(msg)
            if msg:
                await msg.edit(content=f"{user.mention} removed {game.name}", embed=None, view=None)

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

            desc = ""
            for table in event.tables.values():
                game = table.game
                players = list(table.players.values())
                desc += f"[{game.name}]({game.link}) [{len(players)}/{game.maxplayers}] - {", ".join(
                    [p.mention for p in players])}\n"

            embed = discord.Embed(
                title="Games being brought", description=desc)

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
                player = self.store.get_player(user.id) or Player(
                    user.id, user.display_name, user.mention)
                table = tables[view.choice]
                logger.info("user: %s/%s selected game %s", user.id,
                            user.display_name,  table.game.name)
                self.store.join_table(player=player, table=table)

        except Exception as e:
            logger.error("Failed to join game", exc_info=True)
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)






