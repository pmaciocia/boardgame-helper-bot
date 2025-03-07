import asyncio
import functools
import sys

from datetime import datetime, time, UTC
from typing import Iterator

import discord
from discord.app_commands import Group
from discord.ext import commands
from discord.ext.commands.bot import Bot


from boardgamegeek import BGGClient, BGGRestrictSearchResultsTo
from boardgamegeek.objects.games import BoardGame

from store import *
from embeds import *
from views import *
from utils import get_message

from cashews import cache, noself

cache.setup("disk://?directory=/tmp/cache&timeout=1&shards=0")

from utils import setup_logging
logger = setup_logging("boardgame.helper.games")

def is_guild_owner():
    def predicate(ctx):
        return ctx.guild is not None and ctx.guild.owner_id == ctx.author.id
    return commands.check(predicate)

class Meetup(commands.Cog):
    def __init__(self, bot: Bot, store: Store, bgg: BGGClient):
        self.bot = bot
        self.store = store
        self.bgg = bgg

    games =  Group(name="games", description="Manage games")
    manage = Group(name="manage", description="Manage events")

    async def on_ready(self):
        logger.info("Setting up events")
        for event in self.store.get_all_events():
            for table in list(event.tables.values()):
                for message in table.messages:
                    if message.type == MessageType.JOIN:
                        logger.info("Add view for table %s - message %d",
                                    table.id, message.id)
                        self.bot.add_view(GameJoinView(
                            table, self.store, self.bot), message_id=message.id)
                
    @commands.check_any(commands.is_owner(), is_guild_owner())
    @manage.command(name='reset', description='Reset the games')
    async def reset(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.store.reset()
        await interaction.followup.send("DB reset", ephemeral=True)
    
    @commands.check_any(commands.is_owner())
    @manage.command(name='sync', description='Resync bot commands')
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.bot.tree.sync()
        await interaction.followup.send("Commands resynced", ephemeral=True)

        
    @commands.check_any(commands.is_owner(), is_guild_owner())
    @manage.command(name='settings', description='Manage settings for this guild')
    async def settings(self, interaction: discord.Interaction):
        view = GuildSettingsView(self.store)
        msg = await interaction.response.send_message("Please select a channel", view=view, ephemeral=True)
        view.message = msg

        await view.wait()
        logger.info("view.await() - channel=%d", view.channel_choice)
    
    @commands.check_any(commands.is_owner(), is_guild_owner())
    @manage.command(name='clean', description='Remove bot messages from today')
    async def clean(self, interaction: discord.Interaction):
        start = datetime.combine(datetime.now(UTC), time.min)
        interaction.channel_id
        channel = await self.bot.fetch_channel(interaction.channel_id)
        await interaction.response.defer()
        await channel.purge(after=start, check=lambda m: m.author == self.bot.user, bulk=True)
        await interaction.followup.send("Messages removed", ephemeral=True)
        
    @manage.command(name='create_event', description='Create a new event')
    async def create_event(self, interaction: discord.Interaction):
        guild = interaction.guild
        logger.info(f"Create event for guild {guild.id}")

        try:
            guild = self.store.get_guild(guild.id) or self.store.add_guild(channel_id=interaction.channel_id, guild_id=guild.id)
            if guild.event:
                response = f"Event already exists"
            else:    
                event = self.store.add_event(guild=guild)
                response = f"Event created"
                
            await interaction.response.send_message(response, ephemeral=True, delete_after=5)
        except Exception as e:
            logger.error("Failed to create event", exc_info=True)
            await interaction.response.send_message(content="Failed", ephemeral=True, delete_after=5)

    @manage.command(name='delete_event', description='Delete the current event')
    async def delete_event(self, interaction: discord.Interaction):
        guild = interaction.guild
        logger.info(f"Delete event for guild {guild.id}")

        try:
            guild = self.store.get_guild(guild.id)
            if guild is None or guild.event is None:
                response = f"No upcoming events for this server"
                await interaction.response.send_message(response, ephemeral=True, delete_after=5)
                return

            event = guild.event

            for table in event.tables.values():
                for message in table.messages:
                    msg = await get_message(self.bot, message.id, message.channel_id)
                    if msg:
                        await msg.delete()

            # cascade delete tables etc.
            self.store.remove_event(event)
            await interaction.response.send_message("Event deleted", ephemeral=True, delete_after=5)
        except Exception as e:
            logger.error("Failed to delete event", exc_info=True)
            await interaction.response.send_message(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='add', description='Add a game you are bringing')
    async def add_game(self, interaction: discord.Interaction, game_name: str, note: str = None):
        user = interaction.user
        guild = interaction.guild

        try:
            guild = self.store.get_guild(guild.id) or self.store.add_guild(channel_id=interaction.channel_id, guild_id=guild.id)
            event = guild.event
            if event is None:
                response = f"No upcoming events for this server"
                await interaction.response.send_message(response, ephemeral=True, delete_after=5)
                return

            logger.info(f"Add game {game_name} for user {user.id}, guild {guild.id}, event {event.id}")

            user_tables = [table for table in event.tables.values() if table.owner.id == user.id]
            if len(user_tables) > 0:
                response = f"You are already bringing a game - {user_tables[0].game.name}"
                await interaction.response.send_message(response, ephemeral=True, delete_after=5)
                return

            await interaction.response.defer(ephemeral=True)
            bgg_games = await self.async_lookup(name=game_name)

            owner = self.store.get_player(user.id) or self.store.add_player(
                Player(user.id, user.display_name, user.mention))

            if len(bgg_games) == 0:
                await interaction.followup.send(content=f"Couldn't find game '{game_name}'")
                return

            if len(bgg_games) == 1:
                game = bgg_games[0]
            else:
                view = GameChooseView(bgg_games)
                message = await interaction.followup.send(
                    content=f"Found {len(bgg_games)} games with the name '{game_name}'",
                    embed=GamesEmbed(game_name, bgg_games[:5]),
                    view=view,
                )
                view.message = message

                timeout = await view.wait()
                if timeout or view.choice is None:
                    return
                game = view.choice

            game = self.store.add_game(game)
            table = self.store.add_table(event, owner, game, note)
            table = self.store.join_table(owner, table)
            if guild.channel_id != interaction.channel_id:
                add_msg = await interaction.followup.send(embed=GameEmbed(table))
                table = self.store.add_table_message(table, Message(add_msg.id, guild.id, interaction.channel_id, MessageType.ADD))

            channel = self.bot.get_channel(guild.channel_id)
            join_view = GameJoinView(table, self.store, self.bot)
            join_message = await channel.send(
                content="Click to join",
                embed=GameEmbed(table, list_players=True, show_note=True),
                view=join_view
            )
            join_view.message = join_message
            table = self.store.add_table_message(table, Message(join_message.id, guild.id, interaction.channel_id, MessageType.JOIN))
        except Exception as e:
            logger.error("Failed to add game", exc_info=True)
            message = await interaction.followup.send(content="Failed", ephemeral=True, delete_after=5)
            await message.delete(delay=5)

    @games.command(name='remove', description='Remove a game you were bringing')
    async def remove_game(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        logger.info(f"Remove game for user {user.id}, guild {guild.id}")

        try:
            guild = self.store.get_guild(guild.id)
            if guild is None or guild.event is None:
                response = f"No upcoming events for this server"
                message = await interaction.response.send_message(response, ephemeral=True, delete_after=5)
                return
            
            event = guild.event
            tables = event.tables
            user_tables = [table for table in tables.values() if table.owner.id == user.id]

            if len(user_tables) == 0:
                response = f"You are not bringing any games"
                await interaction.response.send_message(response, ephemeral=True, delete_after=5)
                return

            for table in user_tables:
                logger.debug("Found table %s in guild %s", table.id, guild.id)
                game = table.game
                players = table.players.values()

                players = ", ".join([p.mention for p in players])
                response = f"Sorry {players}, but {user.display_name} is not bringing {game.name} anymore!"
                await interaction.response.send_message(response)

                messages = table.messages
                if len(messages) == 0:
                    continue

                for message in messages:
                    logger.debug("Process message %d for table %s", message.id, table.id)
                    msg = await get_message(self.bot, message.id, message.channel_id)
                    if msg:
                        await msg.edit(content=f"{user.mention} removed {game.name}", embed=None, view=None)
                    else:
                        logger.debug("Message %d not found - removing", message.id)
                        self.store.delete_message(message)

                self.store.remove_table(table)

        except Exception as e:
            logger.error("Failed to remove game", exc_info=True)
            await interaction.response.send_message(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='list', description='List games that people are bringing')
    async def list_games(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        logger.info(f"List games for user {user.id}, guild {guild.id}")

        try:
            guild = self.store.get_guild(guild.id)
            if guild is None or guild.event is None:
                response = f"No upcoming events for this server"
                await interaction.response.send_message(response)
                return
            
            event = guild.event
            if len(event.tables) == 0:
                response = f"No games yet for the next event"
                await interaction.response.send_message(response)
                return

            desc = ""
            for table in event.tables.values():
                game = table.game
                players = list(table.players.values())
                desc += f"[{game.name}]({game.link}) [{len(players)}/{game.maxplayers}] - {", ".join(
                    [p.mention for p in players])}\n"

            embed = discord.Embed(
                title="Games being brought", description=desc)

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error("Failed to list games", exc_info=True)
            await interaction.response.send_message(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='players', description='List people that want to play your game')
    async def list_players(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        logger.info(f"List players for user {user.id}, guild {guild.id}")

        try:
            guild = self.store.get_guild(guild.id)
            if guild is None or guild.event is None:
                response = f"No upcoming events for this server"
                await interaction.response.send_message(response, ephemeral=True)
                return
            event = guild.event
            
            player = self.store.get_player(user.id)
            if player is None or event.tables[player.id] is None:
                response = f"{user.mention}, you are not bringing any games"
                await interaction.response.send_message(response, ephemeral=True, delete_after=5)
                return
            
            table = event.tables[player.id]
            await interaction.response.send_message(embed=PlayerListEmbed(table), ephemeral=True)
        except Exception as e:
            logger.error("Failed to list players", exc_info=True)
            await interaction.response.send_message(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='join', description='Join a game that someone is bringing')
    async def join_game(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        try:
            guild = self.store.get_guild(guild.id)
            if guild is None or guild.event is None:
                response = f"No upcoming events for this server"
                await interaction.response.send_message(response, ephemeral=True)
                return
            event = guild.event

            tables = list(event.tables.values())
            if len(tables) == 0:
                await interaction.response.send_message(f"{user.mention}, No-one is bringing any games yet!", ephemeral=True)
                return

            embed = GameEmbed(tables[0])
            view = GameListView(event=event, store=self.store)
            msg = await interaction.response.send_message("Pick a game", embed=embed, view=view, ephemeral=True)
            view.message = msg

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
            await interaction.response.send_message(content="Failed", ephemeral=True, delete_after=5)

    @noself(cache)(ttl="24h")
    async def async_lookup(self, name=None, id=None) -> Iterator[Game]:
        return await run_sync_method(self.lookup, name=name, id=id)

    def lookup(self, name=None, id=None) -> Iterator[Game]:
        if not (name or id):
            return []

        logger.info("doing lookup id=%s name=%s", id, name)

        if id:
            game = bgg_to_game(self.bgg.game(game_id=id))
            return [game] if game else []
        if name:
            search = self.bgg.search(
                name, search_type=[BGGRestrictSearchResultsTo.BOARD_GAME,
                                   BGGRestrictSearchResultsTo.BOARD_GAME_EXPANSION]
            )

            logger.info("found %d games for search %s", len(search), name)

            ids = [game.id for game in search]
            games = []
            for group in [ids[i:i + 20] for i in range(0, len(ids), 20)]:
                gs = self.bgg.game_list(group)
                games.extend(bgg_to_game(bg) for bg in gs)

            return sorted(games, key=lambda g: g.rank or sys.maxsize)


def bgg_to_game(bg: BoardGame) -> Game:
    if bg is None:
        return None

    r = max((rank.best, rank.player_count)
            for rank in bg._player_suggestion)[1]
    return Game(
        id=bg.id,
        name=bg.name,
        year=bg.year,
        rank=bg.boardgame_rank,
        description=bg.description,
        thumbnail=bg.thumbnail,
        minplayers=bg.minplayers,
        maxplayers=bg.maxplayers,
        recommended_players=r
    )

async def run_sync_method(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    func_call = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)
