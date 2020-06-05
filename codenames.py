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
    
CAPT = '👑'

class Codenames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game = None

    @commands.command(name='_reset', hidden=True)
    @commands.is_owner()
    async def reset(self, ctx):
        logger.info(f"Resetting...")
        self.game.reset()
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

        self.game = Game(message)

    @commands.command(name='_stop_game', help='Stop a game')
    async def remove_game(self, ctx):
        user = ctx.message.author
        logger.info(f"Stopping game for user {user.id}")
        
        response = "Game over!"
        await ctx.send(response)

    @commands.command(name='_list_players', help='List games that people are bringing')
    async def list_players(self, ctx):
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

        if reaction.emoji not in set(t.value for t in Team) and reaction.emoji != CAPT:
            logger.info(f"Unknown reaction {reaction.emoji} - removing")
            await message.clear_reaction(reaction.emoji)

        logger.info(f"Game message is {game.message.id}")
        if message.id == game.message.id:
            logger.info(f"Reactions are {message.reactions} ")
            teams = { 
                user: r
                for r in message.reactions
                for user in await r.users().flatten()
                if reaction.emoji != r.emoji and
                    r.emoji in [Team.RED.value, Team.BLUE.value] 
                    and not user.bot
            }

            logger.info(teams)

            prefix = "{reaction.emoji} - "

            if reaction.emoji in set(t.value for t in Team):
                team = Team(reaction.emoji)
                other = team.other

                if user in teams:
                    logger.info(f"Removing {user.id} from {other.name} team")
                    await teams[user].remove(user)
                    del teams[user]

                #game.add_player(user, team)
                logger.info(f"Adding {user.id} to {team.name} team")
                
                if user.nick is None or not user.nick.starts_with(prefix):
                    await user.edit(nick=f"{prefix}{user.nick or user.name}")

            elif reaction.emoji == CAPT:
                if user in teams:
                    if user.nick is None or not user.nick.starts_with(prefix):
                        await user.edit(nick=f"{prefix}{user.nick or user.name}")
                    

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        logger.info(f"User {user.id} removed reaction {reaction.emoji} for message {reaction.message.id}")

        prefix = "{reaction.emoji} - "

        if user.nick != None and user.nick.starts_with(prefix):
            await user.edit(nick=user.nick[len(prefix):])
        

class Game():

    def __init__(self, message):
        self.reset()
        self.message = message
    
    def reset(self):
        self.players = {
            Team.RED: set(),
            Team.BLUE: set()
        }

        self.captains = {
            Team.RED: None,
            Team.BLUE: None
        }

    def add_player(self, user, team):
        self.players[team].add(user)

    def remove_player(self, user, team):
        if user in self.players[team]:
            self.players[team].remove(user)

    def add_captain(self, user, team):
        self.captains[team] = user

    def list_players(self):
        return ( (self.captains[team], self.players[team]) for team in Team )

