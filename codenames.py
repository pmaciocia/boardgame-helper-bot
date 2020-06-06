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
        return set(t.value for t in cls)

CAPT = '👑'

class Codenames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.self = None
        self.players = []

    @commands.command(name='_reset', hidden=True)
    @commands.is_owner()
    async def reset(self, ctx: commands.Context):
        logger.info(f"Resetting...")
        self.players.clear()
        await game.delete()
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

    @commands.command(name='_list_players', help='List games that people are bringing')
    async def list_players(self, ctx: commands.Context):
        user = ctx.message.author

        if self.game is None:
            await ctx.send(f"{user.mention}, there is no game in progress!")
            return

        players = self.game.list_players()

        for captain, team in players:
            response = f"{captain} - {', '.join(player.name for player in team)}"
            await ctx.send(response)


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        logger.info(f"User {user.id} reacted with {reaction.emoji} for message {reaction.message.id}")

        message = reaction.message

        if user.bot:
            logger.info(f"User {user.id} is a bot - ignoring")
            return

        game = self.game 
        if game is None:
            logger.info(f"No game in progress - ignoring")
            return

        if reaction.emoji not in Team.values() and reaction.emoji != CAPT:
            logger.info(f"Unknown reaction {reaction.emoji} - removing")
            return

        logger.info(f"Game message is {self.game_message.id}")
        if message == self.game_message:
            logger.info(f"Reactions are {message.reactions} ")

            player = Player(user)
            if player not in self.players:
                self.players.add(player)
            
            player.assign_from_reaction(reaction)
            
                    

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        logger.info(f"User {user.id} removed reaction {reaction.emoji} for message {reaction.message.id}")

        prefix = "{reaction.emoji} - "

        if user.nick != None and user.nick.starts_with(prefix):
            await user.edit(nick=user.nick[len(prefix):])
        
class Player:
    def __init__(self, user: discord.Member):
        self.user = user
        self.prefix = None
        self.is_captain = False
        self.team = None

    async def remove_nick(self):
        if self.prefix:
            await user.edit(nick=user.nick[len(self.prefix):])
            self.prefix = None

    async def set_nick(self):
        if prefix:
            await user.edit(nick=f"{prefix}{user.nick or user.name}")

    async def assign_from_reaction(self, reaction: discord.Reaction):
        emoji = reaction.emoji
        if emoji not in Team.values() or emoji != CAPT:
            return
    
        message = reaction.message
        if self.team is None:
            if emoji in Team.values():
                self.team = Team(emoji)
                self.prefix = f"{self.team.value} -"

        else:
            if emoji == CAPT:
                self.is_captain = True
                self.remove_nick()
                self.prefix = self.prefix = f"{CAPT}{self.team.value} -"
                
            else:
                # Can't react with same emoji twice
                r_team = Team(emoji)

                self.is_captain = False
                self.team = r_team
                
                self.remove_nick()
                self.prefix = f"{self.team.value} -"

            self.set_nick()


