import discord
from environs import Env
from discord.ext import commands

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("boardgame.helper")
logger.setLevel(logging.DEBUG)

env = Env()
env.read_env()

token = env.str("DISCORD_TOKEN")

def main():
    bot = commands.Bot(intents=discord.Intents.default())
    async def on_ready():
        logger.info('%s has connected to Discord!', bot.user)

    bot.add_listener(on_ready)
    bot.add_check(commands.guild_only())
    bot.load_extension("bgg")
    bot.load_extension("meetup")
    bot.run(token)

if __name__ == "__main__":
    main()
