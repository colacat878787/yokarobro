import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': 'True',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []

    @commands.command(name='加入')
    async def join(self, ctx):
        if not ctx.message.author.voice:
            await ctx.send("嗷～你沒在語音頻道耶！")
            return
        channel = ctx.message.author.voice.channel
        try:
            if ctx.voice_client:
                if ctx.voice_client.channel.id != channel.id:
                    await ctx.voice_client.move_to(channel)
            else:
                await channel.connect(timeout=60.0, reconnect=True)
            await ctx.send(f"✅ 洛洛成功降落於語音頻道 `{channel.name}`！")
        except discord.errors.ConnectionClosed as e:
            if e.code == 4017:
                print("⚠️ [警告] 發生 4017 卡房錯誤，正在強制切斷重新連線...")
                await ctx.guild.change_voice_state(channel=None)
                await asyncio.sleep(2)
                await channel.connect(timeout=60.0, reconnect=True)
                await ctx.send(f"🔄 洛洛已清除幽靈連線並重新降落！")
            else:
                await ctx.send(f"嗷～語音伺服器連線意外關閉：{e}")
        except Exception as e:
            await ctx.send(f"嗷～嘗試連線失敗：{e}")

    @commands.command(name='播放')
    async def play(self, ctx, *, search):
        async with ctx.typing():
            try:
                if not ctx.voice_client:
                    if not ctx.message.author.voice:
                        await ctx.send("嗷～你沒在語音頻道耶！")
                        return
                    channel = ctx.author.voice.channel
                    try:
                        voice_client = await channel.connect(timeout=60.0, reconnect=True)
                    except discord.errors.ConnectionClosed as e:
                        if e.code == 4017:
                            print("⚠️ [警告] 發生 4017 卡房錯誤，正在強制切斷重新連線...")
                            await ctx.guild.change_voice_state(channel=None)
                            await asyncio.sleep(2)
                            voice_client = await channel.connect(timeout=60.0, reconnect=True)
                        else:
                            await ctx.send(f"嗷～嘗試連線失敗：{e}")
                            return
                    except Exception as e:
                        await ctx.send(f"嗷～嘗試連線失敗：{e}")
                        return
                else:
                    voice_client = ctx.voice_client
                    
                player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True)
                
                if voice_client.is_playing():
                    self.queue.append(player)
                    await ctx.send(f"嗷～音樂已加入播放清單：**{player.title}**")
                else:
                    voice_client.play(player, after=lambda e: self.play_next(ctx))
                    await ctx.send(f"嗷～開始播放：**{player.title}**")
            except Exception as e:
                await ctx.send(f"嗷嗷嗷～播放失敗：{e}")

    def play_next(self, ctx):
        if self.queue and ctx.voice_client:
            player = self.queue.pop(0)
            ctx.voice_client.play(player, after=lambda e: self.play_next(ctx))
            asyncio.run_coroutine_threadsafe(ctx.send(f"嗷～下一首：**{player.title}**"), self.bot.loop)

    @commands.command(name='停止')
    async def stop(self, ctx):
        if ctx.voice_client:
            ctx.voice_client.stop()
            await ctx.voice_client.disconnect()
            self.queue.clear()
            await ctx.send("洛洛下班啦，大家掰掰！")

    @commands.command(name='跳過')
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("嗷～跳過這首歌！")

    @commands.command(name='強制跳過')
    @commands.has_permissions(administrator=True)
    async def force_skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("🚨 管理員強制跳過了這首歌！")
            
    @commands.command(name='插歌')
    @commands.has_permissions(administrator=True)
    async def insert_play(self, ctx, *, search):
        async with ctx.typing():
            try:
                if not ctx.voice_client:
                    if not ctx.message.author.voice:
                        await ctx.send("嗷～你沒在語音頻道耶！")
                        return
                    channel = ctx.author.voice.channel
                    try:
                        voice_client = await channel.connect(timeout=60.0, reconnect=True)
                    except Exception as e:
                        await ctx.send(f"嗷～嘗試連線失敗：{e}")
                        return
                else:
                    voice_client = ctx.voice_client
                    
                player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True)
                
                if voice_client.is_playing():
                    self.queue.insert(0, player)
                    await ctx.send(f"🚨 管理員強制插歌！**{player.title}** 將在下一首立刻播放！")
                else:
                    voice_client.play(player, after=lambda e: self.play_next(ctx))
                    await ctx.send(f"🚨 管理員強制插歌！開始播放：**{player.title}**")
            except Exception as e:
                await ctx.send(f"嗷嗷嗷～插歌失敗：{e}")

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
