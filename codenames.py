import logging
import discord
from collections import defaultdict
from enum import Enum

import sys

from discord.ext import commands

logger = logging.getLogger("boardgame.helper.games")

RED_TEAM = '🔴'
BLUE_TEAM = '🔵'

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

        game = self.game 
        if game is None:
            return

        logger.info(f"Game message is {game.message.id}")
   
        if reaction.message.id == game.message.id:
            logger.info(f"Reaction matches game!")
            
            if reaction.emoji in Team:
                team = Team(reaction.emoji)
                game.add_player(user, team)
                logger.info(f"Adding {user.id} to {team} team")
                await user.edit(nick=f"{reaction.emoji} - {user.nick}")

            elif reaction.emoji == RED_CAPT:
                game.add_captain(user, Team.RED)
                logger.info(f"Adding {user.id} as red team captain")
                await user.edit(nick=f"{RED_TEAM}{RED_CAPT} - {user.nick}")


class Team(Enum):
    RED = '🔴'
    BLUE = '🔵'


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

