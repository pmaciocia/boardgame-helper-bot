from discord.ext.commands.bot import Bot
from discord import Message
from discord.utils import _ColourFormatter
from discord.errors import NotFound

import logging, colorlog

async def get_message(bot: Bot, message_id: int, channel_id: int) -> Message:
    try:
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        if channel:
            return await channel.fetch_message(message_id)
    except NotFound:
        return None    
 
 
def setup_logging(name: str, level: int = logging.DEBUG) -> logging.Logger:

    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = colorlog.StreamHandler()
        handler.setFormatter(_ColourFormatter())
        logger.addHandler(handler)
        
    logger.setLevel(level)
    return logger