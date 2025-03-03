from discord.ext.commands.bot import Bot
from discord import Message
from discord.errors import NotFound

async def get_message(bot: Bot, message_id: int, channel_id: int) -> Message:
    try:
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        if channel:
            return await channel.fetch_message(message_id)
    except NotFound:
        return None    
 