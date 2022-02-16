import asyncio
from importlib.abc import SourceLoader
import logging
from re import S
import discord
from discord.ext import commands
from discord.ext.commands.core import command

from random import shuffle

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
        self.player = None
        self.is_playing = False
        self.music_queue = []

    @commands.command()
    @commands.has_any_role(*voice_channel_moderator_roles)
    async def summon(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""
        logger.info(f"Summoned to {channel.guild}/{channel.name} by {ctx.author}")

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)
        
        await channel.connect()

    @commands.command()
    @commands.has_any_role(*voice_channel_moderator_roles)
    async def play(self, ctx, *, song):
        logger.info(f"play command - song:'{song}' author:'{ctx.author}'")
        
        """Streams from a url (same as yt, but doesn't predownload)"""
        await self.queue_song(ctx, song)
        
        if len(self.music_queue) > 0 and not self.is_playing:
            await self.play_music(ctx)
            
    
    @commands.command()
    @commands.has_any_role(*voice_channel_moderator_roles)
    async def skip(self, ctx):
        logger.info(f"skip command - author:{ctx.author}")
        
        if self.is_playing and ctx.voice_client:
            ctx.voice_client.stop()
            await self.play_music(ctx)
            

    @commands.command()
    async def queue(self, ctx):
        logger.info(f"queue command - author:'{ctx.author}'")

        if len(self.music_queue) > 0:
            embed = discord.Embed(title=f"Song queue")
            text = ""
            for (n, (player,_))  in enumerate(self.music_queue):
                text += f"{n+1}. **{player.title}**\n"
            
            embed.description = text
            await ctx.send(embed=embed)
        else: 
            await ctx.send(f":shrug: Queue is empty")


    @commands.command()
    @commands.has_any_role(*voice_channel_moderator_roles)
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""
        logger.info(f"volume command - volume:'{volume}' author:'{ctx.author}'")

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        volume = max(0, min(volume, 100))
       
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.command()
    @commands.has_any_role(*voice_channel_moderator_roles)
    async def pause(self, ctx):
        """Stops and disconnects the bot from voice"""
        logger.info(f"stop command - author:'{ctx.author}'")

        if ctx.voice_client is not None:
            if ctx.voice_client.paused():
                await ctx.voice_client.resume()
                await ctx.send(f":arrow_forward: Resuming the music")
            elif ctx.voice_client.is_playing():    
                await ctx.voice_client.pause()
                await ctx.send(f":pause_button: Pausing the music")
            
    @commands.command()
    @commands.has_any_role(*voice_channel_moderator_roles)
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        logger.info(f"stop command - author:'{ctx.author}'")

        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()
            
        self.reset()

    @commands.command()
    @commands.has_any_role(*voice_channel_moderator_roles)
    async def solo(self, ctx):
        """Stops and disconnects the bot from voice"""
        logger.info(f"solo command - author:'{ctx.author}'")

        await self.queue_song(ctx, solo)
        
        if len(self.music_queue) > 0 and not self.is_playing:
            await self.play_music(ctx)
    
    async def queue_song(self, ctx, song):                
        async with ctx.typing():
            players = await YTDLSource.from_url(song, loop=self.bot.loop)
            if players is None or len(players) == 0: 
                await ctx.send(f":shrug: Couldn't find **{song}** -- requested by {ctx.author.mention}")
            else:
                text = ""
                q_msg = not self.is_playing and len(players) > 1
                for player in players:
                    logger.info(f"adding song {player.title}")
                    
                    text += f":musical_note: Added **{player.title}** to the queue\n"
                    self.music_queue.append((player,ctx.author.mention))
                    if not self.is_playing:
                        await self.play_music(ctx)
                
                if q_msg:
                    await ctx.send(embed=discord.Embed(description=text))                                    
        
    def play_next(self, ctx):        
        if len(self.music_queue) == 0:
            self.is_playing = False
            ctx.voice_client.stop()
        else:
            (player, author) = self.music_queue.pop(0)
            ctx.voice_client.play(player, after=lambda e: self.play_next(ctx))
            ctx.send(embed=discord.Embed(description=f":arrow_forward: Playing **{player.title}** -- requested by {author}"))


    async def play_music(self, ctx):
        if len(self.music_queue) == 0:
            await ctx.send(f":confused: No songs in the queue")
            self.reset()
        else:
            self.is_playing = True
            (player, author) = self.music_queue.pop(0)
            self.current_song = player
            await ctx.send(embed=discord.Embed(description=f":arrow_forward: Playing **{player.title}** -- requested by {author}"))
            ctx.voice_client.play(player)

                


    @play.before_invoke
    @solo.before_invoke
    async def ensure_voice(self, ctx):
        logger.info("ensuring voice connection")
        if ctx.voice_client is None:
            if ctx.author.voice:
                logger.info(f"connecting to {ctx.author.voice.channel.name}")
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError(
                    "Author not connected to a voice channel.")
            
    def reset(self):
        self.voice = None
        self.current_song = None
        self.is_playing = False
        self.music_queue = []

