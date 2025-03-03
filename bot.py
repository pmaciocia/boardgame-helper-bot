import discord
from environs import Env
from discord.ext import commands

from bgg import BGGClient
from meetup import Meetup
from store.local import SQLiteStore
from bgg import BGGCog

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("boardgame.helper")
logger.setLevel(logging.DEBUG)

env = Env()
env.read_env()

token = env.str("DISCORD_TOKEN")


class BoardgameHelperBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):   
        store = SQLiteStore()
        meetup = Meetup(self, store, BGGClient(timeout=10))
        self.add_listener(meetup.on_ready, "on_ready")
        self.add_check(commands.guild_only())
        await self.add_cog(meetup)
        await self.add_cog(BGGCog(self))
        await self.tree.sync()
        
    async def on_ready(self):
        logger.info('%s has connected to Discord!', self.user)

def main():
    bot = BoardgameHelperBot()
    bot.run(token)

if __name__ == "__main__":
    main()
