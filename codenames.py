import logging
import discord
from collections import defaultdict
from enum import Enum

import sys

from discord.ext import commands

logger = logging.getLogger("boardgame.helper.games")

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

CAPT = '👑'

class Codenames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game = None
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

    @command.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        pass


class Player:
    def __init__(self, user: discord.Member):
        self.user = user
        self.prefix = None
        self.is_captain = False
        self.team = None

    async def remove_nick(self):
        if self.prefix and self.user.nick:
            nick = self.user.nick[len(self.prefix):]
            logger.info(f"Resetting user {self.user.id} nick to {nick}")
            try:
                await self.user.edit(nick=nick)
            except:
                logger.error(f"Failed to remove nick for user {self.user.id}")
            self.prefix = None

    async def update_nick(self):
        if self.prefix:
            await self.remove_nick()

        self.prefix = f"{CAPT if self.is_captain else ''} {self.team.value} - "
        nick = f"{self.prefix}{self.user.nick or self.user.name}"

        logger.info(f"Setting user {self.user.id} nick to {nick}")
        try:
            await self.user.edit(nick=nick)
        except:
            logger.error(f"Failed to set nick for user {self.user.id}")

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
       

