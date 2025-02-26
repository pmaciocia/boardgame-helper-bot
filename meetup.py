import logging
import discord
import asyncio
import functools
import sys
from datetime import datetime, time, UTC
from typing import Iterator

from discord.ext import commands
from discord.commands import SlashCommandGroup
from boardgamegeek import BGGClient, BGGRestrictSearchResultsTo
from boardgamegeek.objects.games import BoardGame

from store import *
from store.local import SQLiteStore
from embeds import *
from views import *

from cashews import cache, noself

cache.setup("disk://?directory=/tmp/cache&timeout=1&shards=0")

logger = logging.getLogger("boardgame.helper.games")

signup_channel = 1339272062946246696


def is_guild_owner():
    def predicate(ctx):
        return ctx.guild is not None and ctx.guild.owner_id == ctx.author.id
    return commands.check(predicate)

class Meetup(commands.Cog):
    def __init__(self, bot: discord.Bot, store: Store, bgg: BGGClient):
        self.bot = bot
        self.store = store
        self.bgg = bgg

    meetup = SlashCommandGroup("meetup", "meetup group")
    games = meetup.create_subgroup("games", "Manage games")
    manage = meetup.create_subgroup("manage", "Manage games")

    async def on_ready(self):
        logger.info("Setting up events")
        for event in self.store.get_all_events():
            for table in list(event.tables.values()):
                for message in table.messages:
                    if message.type == MessageType.JOIN:
                        logger.info("Add view for table %s - message %d",
                                    table.id, message.id)
                        self.bot.add_view(GameJoinView(
                            table, self.store), message_id=message.id)
                
    @commands.check_any(commands.is_owner(), is_guild_owner())
    @manage.command(name='reset', help='Reset the games')
    async def reset(self, ctx: discord.ApplicationContext):
        self.store.reset()
        await ctx.defer()
    
    @commands.check_any(commands.is_owner())
    @manage.command(name='sync', help='Resync bot commands')
    async def sync(self, ctx: discord.ApplicationContext):
        self.bot.sync_commands()
        await ctx.defer()
        
    @commands.check_any(commands.is_owner(), is_guild_owner())
    @manage.command(name='settings', help='Manage settings for this guild')
    async def settings(self, ctx: discord.ApplicationContext):
        view = GuildSettingsView(self.store)
        msg = await ctx.respond("Please select a role and channel", view=view, ephemeral=True)
        view.message = msg

        self.bot.delete_messages()

        await view.wait()
        logger.info("view.await() - role=%d channel=%d", view.role_choice, view.channel_choice)
    
    @commands.check_any(commands.is_owner(), is_guild_owner())
    @manage.command(name='clean', help='Remove bot messages from today')
    async def clean(self, ctx: discord.ApplicationContext):
        start = datetime.combine(datetime.now(UTC), time.min)
        channel = await self.bot.fetch_channel(ctx.channel_id)
        await ctx.defer()
        await channel.purge(after=start, check=lambda m: m.author == self.bot.user, bulk=False)

    @games.command(name='add', help='Add a game you are bringing')
    async def add_game(self, ctx: discord.ApplicationContext, game_name: str):
        user = ctx.author
        guild = ctx.guild

        try:
            guild = self.store.get_guild(guild.id) or self.store.add_guild(channel_id=ctx.channel_id, guild_id=guild.id)
            event = guild.event
            if event is None:
                event = self.store.add_event(guild=guild)

            logger.info(f"Add game {game_name} for user {user.id}, guild {guild.id}, event {event.id}")

            user_tables = [table for table in event.tables.values() if table.owner.id == user.id]
            if len(user_tables) > 0:
                response = f"You are already bringing a game - {user_tables[0].game.name}"
                await ctx.respond(response, ephemeral=True, delete_after=5)
                return

            await ctx.defer(ephemeral=True)
            bgg_games = await self.async_lookup(name=game_name)

            owner = self.store.get_player(user.id) or self.store.add_player(
                Player(user.id, user.display_name, user.mention))

            if len(bgg_games) == 0:
                await ctx.respond(content=f"Couldn't find game '{game_name}'")
                return

            if len(bgg_games) == 1:
                game = bgg_games[0]
            else:
                view = GameChooseView(bgg_games)
                message = await ctx.respond(
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
            table = self.store.add_table(event, owner, game)
            if guild.channel_id != ctx.channel_id:
                add_msg = await ctx.respond(embed=GameEmbed(table))
                table = self.store.add_table_message(table, Message(add_msg.id, guild.id, ctx.channel_id, MessageType.ADD))

            channel = self.bot.get_channel(guild.channel_id)
            join_view = GameJoinView(table, self.store)
            join_message = await channel.send(
                content="Click to join",
                embed=GameEmbed(table, list_players=True),
                view=join_view
            )
            join_view.message = join_message
            table = self.store.add_table_message(table, Message(join_message.id, guild.id, ctx.channel_id, MessageType.JOIN))
        except Exception as e:
            logger.error("Failed to add game", exc_info=True)
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='remove', help='Remove a game you were bringing')
    async def remove_game(self, ctx: discord.ApplicationContext):
        user = ctx.author
        guild = ctx.guild
        logger.info(f"Remove game for user {user.id}, guild {guild.id}")

        try:
            guild = self.store.get_guild(guild.id)
            if guild is None or guild.event is None:
                response = f"No upcoming events for this server"
                await ctx.respond(response)
                return
            
            event = guild.event
            tables = event.tables
            user_tables = [table for table in tables.values() if table.owner.id == user.id]

            if len(user_tables) == 0:
                response = f"You are not bringing any games"
                await ctx.respond(response)
                return

            for table in user_tables:
                logger.debug("Found table %s in guild %s", table.id, guild.id)
                game = table.game
                players = table.players.values()

                players = ", ".join([p.mention for p in players])
                response = f"Sorry {players}, but {user.display_name} is not bringing {game.name} anymore!"
                await ctx.respond(response, embeds=None)

                messages = table.messages
                if len(messages) == 0:
                    continue

                for message in messages:
                    logger.debug("Process message %d for table %s", message.id, table.id)
                    msg = self.bot.get_message(message.id)
                    if not msg:
                        logger.debug("Try find message %d for channel %d", message.id, message.channel_id)
                        channel = await self.bot.fetch_channel(message.channel_id)
                        message = await channel.fetch_message(message.id)
                    
                    if msg:
                        await msg.edit(content=f"{user.mention} removed {game.name}", embed=None, view=None)
                    else:
                        logger.debug("Message %d not found - removing", message.id)
                        self.store.delete_message(message)

                self.store.remove_table(table)

        except Exception as e:
            logger.error("Failed to remove game", exc_info=True)
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)

    @games.command(name='list', help='List games that people are bringing')
    async def list_games(self, ctx: discord.ApplicationContext):
        user = ctx.author
        guild = ctx.guild

        logger.info(f"List games for user {user.id}, guild {guild.id}")

        try:
            guild = self.store.get_guild(guild.id)
            if guild is None or guild.event is None:
                response = f"No upcoming events for this server"
                await ctx.respond(response)
                return
            
            event = guild.event
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
            guild = self.store.get_guild(guild.id)
            if guild is None or guild.event is None:
                response = f"No upcoming events for this server"
                await ctx.respond(response, ephemeral=True)
                return
            
            event = guild.event
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
            guild = self.store.get_guild(guild.id)
            if guild is None or guild.event is None:
                response = f"No upcoming events for this server"
                await ctx.respond(response, ephemeral=True)
                return
            event = guild.event

            tables = list(event.tables.values())
            if len(tables) == 0:
                await ctx.respond(f"{user.mention}, No-one is bringing any games yet!", ephemeral=True)
                return

            embed = GameEmbed(tables[0])
            view = GameListView(event=event, store=self.store)
            msg = await ctx.respond("Pick a game", embed=embed, view=view, ephemeral=True)
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
            await ctx.respond(content="Failed", ephemeral=True, delete_after=5)

    @noself(cache)(ttl="24h")
    async def async_lookup(self, name=None, id=None) -> Iterator[Game]:
        return await run_sync_method(self.lookup, name=name, id=id)

    def lookup(self, name=None, id=None) -> Iterator[Game]:
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

def setup(bot):
    store = SQLiteStore()
    meetup = Meetup(bot, store, BGGClient(timeout=10))
    bot.add_listener(meetup.on_ready, "on_ready")
    bot.add_cog(meetup)


async def run_sync_method(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    func_call = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)
