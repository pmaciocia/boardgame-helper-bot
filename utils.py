import discord

async def get_message(bot: discord.Bot, message_id: int, channel_id: int) -> discord.Message:
    msg = bot.get_message(message_id)
    if msg is None:
        try:
            channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
            if channel:
                msg = await channel.fetch_message(message_id)
        except discord.NotFound:
            pass
    return msg
    
 