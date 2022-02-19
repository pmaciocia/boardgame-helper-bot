import asyncio
import logging
from collections import defaultdict
from typing import List

import discord
from discord.ext import commands
from discord.ext.commands.core import command

import youtube_dl
from youtube_dl import YoutubeDL

logger = logging.getLogger("boardgame.helper.music")

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ""

voice_channel_moderator_roles = ["DJ", "Moderator", "Mod"]
guild_ids = [
    623882469510217734
]
solo = "https://www.youtube.com/playlist?list=PLxlYTqdTkYe_SQYSUpZKFHJJ8NLY0wjlm"

ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    # Bind to ipv4 since ipv6 addresses cause issues at certain times
    "source_address": "0.0.0.0",
}

ffmpeg_options = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data

        self.title = data.get("title")
        self.url = data.get("url")

    @classmethod
    async def from_url(cls, url, *, loop=None):
        logger.info(f"Searching for {url}")
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        
        if data is None: 
            logger.info("No song found")
            return None

        songs = []
        if "entries" in data:
            logger.info("Found playlist with {0} entries".format(len( data["entries"] )))
            songs = [cls(discord.FFmpegPCMAudio(e["url"], **ffmpeg_options), data=e) for e in data["entries"]]
        else:
            songs.append(cls(discord.FFmpegPCMAudio(data["url"], **ffmpeg_options), data=data))
                
        return songs

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_queue = defaultdict(list)
        
    @commands.command()
    @commands.check_any(
        commands.is_owner(),
        commands.has_any_role(*voice_channel_moderator_roles)
    )
    async def summon(self, ctx):
        """Joins a voice channel"""
        logger.info(f"Summoned! author:'{ctx.author}'")

    @commands.command()
    @commands.check_any(
        commands.is_owner(),
        commands.has_any_role(*voice_channel_moderator_roles)
    )
    async def play(self, ctx, *, song):
        logger.info(f"play command - song:'{song}' author:'{ctx.author}' guild:'{ctx.guild}'")
        
        music_queue = self.music_queue[ctx.guild.id]
        
        """Streams from a url (same as yt, but doesn't predownload)"""
        await self.queue_song(ctx, song)
        
        if len(music_queue) > 0 and not ctx.voice_client.is_playing():
            await self.play_music(ctx)
            
    
    @commands.command()
    @commands.check_any(
        commands.is_owner(),
        commands.has_any_role(*voice_channel_moderator_roles)
    )
    async def skip(self, ctx):
        logger.info(f"skip command - author:{ctx.author}")
        
        if ctx.voice_client:
            ctx.voice_client.stop()
            #await self.play_music(ctx)
            

    @commands.command()
    @commands.check_any(
        commands.is_owner(),
        commands.has_any_role(*voice_channel_moderator_roles)
    )
    async def queue(self, ctx):
        logger.info(f"queue command - author:'{ctx.author}'")

        music_queue = self.music_queue[ctx.guild.id]

        if len(music_queue) > 0:
            embed = discord.Embed(title=f"Song queue")
            text = ""
            for (n, (player,_))  in enumerate(music_queue):
                text += f"{n+1}. **{player.title}**\n"
            
            embed.description = text
            await ctx.send(embed=embed)
        else: 
            await ctx.send(f":shrug: Queue is empty")


    @commands.command()
    @commands.check_any(
        commands.is_owner(),
        commands.has_any_role(*voice_channel_moderator_roles)
    )
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""
        logger.info(f"volume command - volume:'{volume}' author:'{ctx.author}'")

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        volume = max(0, min(volume, 100))
       
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")


    @commands.command()
    @commands.check_any(
        commands.is_owner(),
        commands.has_any_role(*voice_channel_moderator_roles)
    )
    async def pause(self, ctx):
        """Stops and disconnects the bot from voice"""
        logger.info(f"stop command - author:'{ctx.author}'")

        if ctx.voice_client is not None:
            if ctx.voice_client.is_paused():
                ctx.voice_client.resume()
                await ctx.send(f":arrow_forward: Resuming the music")
            elif ctx.voice_client.is_playing():    
                ctx.voice_client.pause()
                await ctx.send(f":pause_button: Pausing the music")
            
            
    @commands.command()
    @commands.check_any(
        commands.is_owner(),
        commands.has_any_role(*voice_channel_moderator_roles)
    )
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        logger.info(f"stop command - author:'{ctx.author}'")

        music_queue = self.music_queue[ctx.guild.id]
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()
            
        music_queue.clear()


    @commands.command()
    @commands.check_any(
        commands.is_owner(),
        commands.has_any_role(*voice_channel_moderator_roles)
    )
    async def solo(self, ctx):
        logger.info(f"solo command - author:'{ctx.author}'")
        
        music_queue = self.music_queue[ctx.guild.id]

        await self.queue_song(ctx, solo)
        
        if len(music_queue) > 0 and not ctx.voice_client.is_playing():
            await self.play_music(ctx)
    
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):        
        if member.id == self.bot.user.id:
            return
        
        voice = member.guild.voice_client
        logger.info(f"voice update voice:{voice} member:{member} before:{before.channel} after:{after.channel}")
        if voice is None:
            return
        
        channel = voice.channel
        if len(channel.members) == 1 and channel.members[0].id == self.bot.user.id:
            logger.info(f"channel empty, wait 20s - channel:{channel}")
            await asyncio.sleep(20)
            if len(channel.members) == 1 and channel.members[0].id == self.bot.user.id:
                logger.info(f"disconnecting from {channel}")
                music_queue = self.music_queue[channel.guild.id]
                await voice.disconnect()
                music_queue.clear()
                
                    
    async def queue_song(self, ctx, song):                
        async with ctx.typing():
            songs = await YTDLSource.from_url(song, loop=self.bot.loop)
            if len(songs) == 0: 
                await ctx.send(f":shrug: Couldn't find **{song}** -- requested by {ctx.author.mention}")
            else:
                text = ""
                music_queue = self.music_queue[ctx.guild.id]
                for song in songs:
                    logger.info(f"adding song {song.title}")
                    
                    text += f":musical_note: Added **{song.title}** to the queue\n"
                    music_queue.append((song,ctx.author.mention))
                
                if len(music_queue) >= 1:
                    await ctx.send(embed=discord.Embed(description=text))                                    
        
        
    async def play_next(self, ctx, voice_client, music_queue):
        if voice_client.is_connected():        
            if len(music_queue) > 0:
                (song, author) = music_queue.pop(0)
                voice_client.play(song, after=lambda e: wrap_await(self.play_next(ctx, voice_client, music_queue),self.bot.loop))
                await ctx.send(embed=discord.Embed(
                    description=f":arrow_forward: Playing **{song.title}** -- requested by {author}"))
        else:
            music_queue.clear()
                
    async def play_music(self, ctx):
        music_queue = self.music_queue[ctx.guild.id]
        if len(music_queue) > 0:
            (song, author) = music_queue.pop(0)
            await ctx.send(embed=discord.Embed(
                description=f":arrow_forward: Playing **{song.title}** -- requested by {author}"))
            ctx.voice_client.play(song, after=lambda e: wrap_await(self.play_next(ctx, ctx.voice_client, music_queue), self.bot.loop))

                
    @play.before_invoke
    @solo.before_invoke
    @skip.before_invoke
    @summon.before_invoke
    async def ensure_voice(self, ctx):
        logger.info("ensuring voice connection")
        if ctx.author.voice:
            logger.info(f"connecting to {ctx.author.voice.channel.name}")
            if ctx.voice_client is None:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.voice_client.move_to(ctx.author.voice.channel)
        else:
            await ctx.send("You are not connected to a voice channel.")
            raise commands.CommandError(
                "Author not connected to a voice channel.")
            

def wrap_await(coro, loop):
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        fut.result()
    except:
        # an error happened sending the message
        pass