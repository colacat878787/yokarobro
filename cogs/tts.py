import discord
from discord.ext import commands
import asyncio
from gtts import gTTS
import os
import uuid

class TTSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 紀錄 {guild_id: text_channel_id}
        self.tts_channels = {}
        # 佇列 {guild_id: [file_path1, file_path2, ...]}
        self.queue = {}
        # 保證在Termux也能撥放的FFmpeg設定
        self.FFMPEG_OPTIONS = {
            'options': '-vn'
        }

    @commands.command(name='say', aliases=['廣播'])
    async def set_tts_channel(self, ctx):
        # 必須在語音頻道內才能綁定
        if not ctx.author.voice:
            await ctx.send("嗷～你必須先在一個語音頻道內，我才知道要把聲音播到哪裡喔！")
            return
            
        self.tts_channels[ctx.guild.id] = ctx.channel.id
        voice_channel = ctx.author.voice.channel
        
        # 嘗試連線
        try:
            if ctx.voice_client:
                await ctx.voice_client.move_to(voice_channel)
            else:
                await voice_channel.connect(timeout=60.0, reconnect=True)
        except Exception as e:
            await ctx.send(f"嗷～糟糕！連接語音失敗惹：{e}")
            return
            
        if ctx.guild.id not in self.queue:
            self.queue[ctx.guild.id] = []
            
        await ctx.send(f"✅ 已綁定本頻道為【AI實況頻道】！洛洛也已經加入 `{voice_channel.name}` 囉！嗷嗷嗷～\n(只要你在這裡打字，我就會唸出來！)")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot or message.is_system() or message.type != discord.MessageType.default:
            return
            
        # 確認是否綁定了這個頻道
        guild_id = message.guild.id
        if guild_id not in self.tts_channels:
            return
        if message.channel.id != self.tts_channels[guild_id]:
            return
        
        # 不要讀取含有指令前綴的文字
        if message.content.startswith(self.bot.command_prefix):
            return

        # 找尋是否有可用的 voice_client
        voice_client = discord.utils.get(self.bot.voice_clients, guild=message.guild)
        if not voice_client or not voice_client.is_connected():
            return
            
        # 產生不重複的音檔名稱
        tts_filename = f"tts_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(os.getcwd(), tts_filename)
        
        try:
            # 轉換文字成語音
            tts = gTTS(text=message.content, lang='zh-tw')
            tts.save(filepath)
            
            # 放入佇列並嘗試播放
            self.queue[guild_id].append(filepath)
            self.play_next(guild_id, voice_client)
            
        except Exception as e:
            print(f"TTS 錯誤: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)

    def play_next(self, guild_id, voice_client):
        # 如果已經在播放音樂或其他TTS，就不介入 (等原先的播完再交由 after callback 呼叫自己)
        if voice_client.is_playing() or not self.queue[guild_id]:
            return
            
        filepath = self.queue[guild_id].pop(0)
        
        # 定義播放結束後要刪除音檔並檢查下一首的回呼函式
        def after_playing(error):
            if os.path.exists(filepath):
                os.remove(filepath)
            # 因為 after 是跑在 thread，要透過 bot.loop 再跑一次 play_next
            if guild_id in self.queue and self.queue[guild_id]:
                self.bot.loop.call_soon_threadsafe(self.play_next, guild_id, voice_client)

        try:
            audio_source = discord.FFmpegPCMAudio(filepath, **self.FFMPEG_OPTIONS)
            voice_client.play(audio_source, after=after_playing)
        except Exception as e:
            print(f"播放 TTS 發生錯誤: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            # 若播放失敗，繼續嘗試下一首
            self.bot.loop.call_soon_threadsafe(self.play_next, guild_id, voice_client)


async def setup(bot):
    await bot.add_cog(TTSCog(bot))
