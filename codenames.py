import logging
import discord
from collections import defaultdict
from enum import Enum

import sys

from discord.ext import commands
import asyncio
from typing import List, Mapping
from random import choice

logger = logging.getLogger("boardgame.helper.games")


CAPT = '👑'

class Team(Enum):
    RED = '🔴'
    BLUE = '🔵'

    @property
    def other(self):
        if self == Team.RED:
            return Team.BLUE
        
        if self == Team.BLUE:
            return Team.RED
    
    @classmethod
    def values(cls):
        return set(t.value for t in Team)

class Player:
    def __init__(self, user: discord.Member):
        self.user = user
        self.previous = None
        self.is_captain = False
        self.team = None

    async def remove_nick(self):
        if self.previous and self.user.nick:
            nick = self.previous

            if not self.user.nick.endswith(nick):
                logger.info(f"User {self.user.id} changed nick since we last changed it")
                self.previous = None
                return 

            await Player._set_nick(self.user, nick)
            self.previous = None

    async def update_nick(self):
        if not self.previous:
            self.previous = self.user.nick or self.user.name

        prefix = f"{CAPT if self.is_captain else ''} {self.team.value} - "
        nick = f"{prefix}{self.previous}"

        await Player._set_nick(self.user, nick)

    @staticmethod
    async def _set_nickname(user, nick):
        logger.info(f"Setting user {user.id} nick to {nick}")
        try:
            await user.edit(nick=nick)
        except:
            logger.error(f"Failed to set nick for user {user.id}")


    async def assign_from_reaction(self, reaction: discord.Reaction):
        emoji = reaction.emoji
        if emoji not in Team.values() and emoji != CAPT:
            logger.info(f"Invalid emoji {emoji}")
            return
    
        message = reaction.message
        if self.team is None:
            logger.info(f"No team assigned for {self.user.id}")
            if emoji in Team.values():
                self.team = Team(emoji)
                await self.update_nick()
        else:
            if emoji == CAPT:
                self.is_captain = True                
            else:
                r_team = Team(emoji)
                self.is_captain = False
                self.team = r_team
            await self.update_nick()



class MonitorChannel:
    channel: discord.VoiceChannel
    players: Mapping[discord.Member, Player]
    teams: Mapping[Team, List[Player]]

    def __init__(self, channel):
        self.channel = channel
        self.players = {m: Player(m) for m in channel.members}
        self.teams = {}

    async def randomise_teams(self):
        if len(self.players) == 0:
            return

        players = sorted(list(self.players.values()), key=lambda p: p.previous or p.user.name)
        red = players[1::2]
        blue = players[::2]

        for player in red:
            player.team = Team.RED

        for player in blue:
            player.team = Team.BLUE
        
        self.teams[Team.RED] = red
        self.teams[Team.BLUE] = blue

        for player in players:
            await player.update_nick()

    async def add_player(self, member: discord.Member):
        if member not in self.players:
            player = Player(member)

            if len(self.players) == 0:
                team = choice(list(Team))
            else:
                team = max(self.teams, key=lambda x: len(self.teams[x])).other

            logger.info(f"Adding user {member.id} to team {team}")

            player.team = team
            self.players[member] = player
            self.teams.setdefault(player.team, []).append(player)
            await player.update_nick()

    async def remove_player(self, member: discord.Member):
        if member in self.players:
            player = self.players[member]
            logger.info(f"Removing user {member.id} from team {player.team.value}")
            await player.remove_nick()
            
            del self.players[member]
            
class Codenames(commands.Cog):
    bot: commands.Bot
    game: discord.Message
    channel: MonitorChannel
    players: Mapping[discord.Member, Player]


    def __init__(self, bot):
        self.bot = bot
        self.game = None
        self.channel = None
        self.players = {}

    @commands.command(name='_reset', hidden=True)
    @commands.is_owner()
    async def reset(self, ctx: commands.Context):
        logger.info(f"Resetting...")
        self.players.clear()
        await self.game.delete()

        self.game = None
        await ctx.message.add_reaction('👌')

    @commands.command(name='_start_game', help='Start a game')
    async def start_game(self, ctx: commands.Context):
        user = ctx.message.author
        logger.info(f"Starting game for user {user.id}")

        response = f"{user.mention} is starting a new game!"
        message = await ctx.send(response)

        for team in Team:
            await message.add_reaction(team.value)

        await message.add_reaction(CAPT)

        self.game = message

    @commands.command(name='_teams', help='Assign teams to a voice channel')
    async def monitor_channel(self, ctx: commands.Context, *, message):
        if len(message) == 0:
            return

        user = ctx.message.author
        channel_name = message

        logger.info(f"Searching for voice channel with name '{channel_name}' for user {user.id} in guild {ctx.guild.id}")       
        channels = [c for c in ctx.guild.channels if type(c) is discord.VoiceChannel and c.name == channel_name]

        if len(channels) == 0:
            logger.info(f"No channel found with name {channel_name}")
            response = f"Sorry, {user.mention} - no channel named '{channel_name}' found"
            message = await ctx.send(response)
            return

        elif len(channels) == 1:
            self.channel = MonitorChannel(channels[0])
            logger.info(f"Found channel {self.channel.channel.id} with name {channel_name}")

        else:
            logger.info(f"Found multiple channels with name {channel_name}")
            
            channels_str = '\n'.join(f"\t[{i}] - {channel.name}" for i, channel in enumerate(channels))
            query = f"I found these channels with that name:\n {channels_str}\n\nWhich one did you mean?"

            def pred(m):
                return m.author == message.author and m.channel == message.channel

            try:
                msg = await self.bot.wait_for('message', check=pred, timeout=60.0)
            except asyncio.TimeoutError:
                await ctx.send('You took too long...')
                return
            

            self.channel = MonitorChannel(channels[int(msg)])
            logger.info(f"Using channel {self.channel.id}")

        await self.channel.randomise_teams()

        

    @commands.command(name='_stop_game', help='Stop a game')
    async def remove_game(self, ctx: commands.Context):
        user = ctx.message.author
        logger.info(f"Stopping game for user {user.id}")
        
        response = "Game over!"
        await ctx.send(response)


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        logger.info(f"User {user.id} reacted with {reaction.emoji} for message {reaction.message.id}")
        
        game = self.game 
        if game is None:
            logger.info(f"No game in progress - ignoring")
            return

        if user.bot:
            logger.info(f"User {user.id} is a bot - ignoring")
            return

        if reaction.emoji not in Team.values() and reaction.emoji != CAPT:
            logger.info(f"Unknown reaction {reaction.emoji} - removing")
            return

        message = reaction.message
        logger.info(f"Game message is {self.game.id}")
        if message.id == self.game.id:
            logger.info(f"Reactions are {message.reactions}")

            if user not in self.players and reaction.emoji == CAPT:
                logger.info(f"User with no team trying to be captain")
                return

            player = self.players.setdefault(user, Player(user))
            await player.assign_from_reaction(reaction)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        logger.info(f"User {user.id} removed reaction {reaction.emoji} for message {reaction.message.id}")
        if user in self.players:
            logger.info(f"Updating player {user.id}")
            player = self.players[user]
            if reaction.emoji == CAPT:
                logger.info(f"Removing captain from player {user.id}")
                player.is_captain = False
                await player.update_nick()
            else:
                logger.info(f"Removing player {user.id}")
                await player.remove_nick()
                del self.players[user]

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if self.channel == None:
            return

        game = self.channel
        if before.channel == game.channel:
            logger.info(f"User {member.id} left game channel {game.channel.id}")
            await game.remove_player(member)
        
        elif after.channel == game.channel:
            logger.info(f"User {member.id} joined game channel {game.channel.id}")
            await game.add_player(member)
