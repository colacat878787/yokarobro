import discord
from discord.ext import commands
import asyncio
import edge_tts
import os
import uuid
import io

class TTSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 紀錄 {guild_id: text_channel_id}
        self.tts_channels = {}
        # 佇列 {guild_id: [file_path1, file_path2, ...]}
        self.queue = {}
        # 標記：是否由 TTS 自己暫停了音樂 {guild_id: bool}
        self.we_paused = {}
        # 被我們暫停的音樂 player {guild_id: OriginalAudioPlayer}，插板完要還原
        self.saved_players = {}
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

        await ctx.send(f"✅ 已綁定本頻道為【AI實況頻道】！Fuwawa也已經加入 `{voice_channel.name}` 囉！嗷嗷嗷～\n(只要你在這裡打字，我就會唸出來！音樂播放時我會自動插播再恢復音樂！)")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot or message.is_system():
            return
        # 讓普通訊息與回覆訊息都可以被唸出來
        if message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return

        # 確認是否綁定了這個頻道
        guild_id = message.guild.id
        if guild_id not in self.tts_channels:
            return
        if message.channel.id != self.tts_channels[guild_id]:
            return
        # 自己剛剛發的廣播說明不念
        if message.author == self.bot.user:
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
            audio_data = await self._generate_audio(message.content)
            if not audio_data:
                raise RuntimeError("TTS 服務沒有回傳任何音訊")

            # 寫入檔案
            with open(filepath, 'wb') as f:
                f.write(audio_data)

            # 放入佇列並嘗試播放
            if guild_id not in self.queue:
                self.queue[guild_id] = []
            self.queue[guild_id].append(filepath)
            self.play_next(guild_id, voice_client)

        except Exception as e:
            print(f"TTS 錯誤（{type(e).__name__}）: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)

    async def _generate_audio(self, text: str) -> bytes:
        """產生 TTS 音訊：edge-tts 失敗時自動退回 gTTS"""
        text = (text or "").strip()
        if not text:
            return b""

        # 1) edge-tts（微軟中文女聲）
        try:
            communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            if audio_data:
                return audio_data
            print("edge-tts 回傳空音訊，改用 gTTS…")
        except Exception as e:
            print(f"edge-tts 失敗（{type(e).__name__}）: {e}，改用 gTTS…")

        # 2) gTTS（Google 翻譯語音）備援（gTTS 是同步庫，丟到執行緒跑）
        from gtts import gTTS
        def _gtts_bytes():
            buf = io.BytesIO()
            gTTS(text=text, lang="zh-TW").write_to_fp(buf)
            buf.seek(0)
            return buf.read()
        return await asyncio.get_running_loop().run_in_executor(None, _gtts_bytes)

    def play_next(self, guild_id, voice_client):
        if not self.queue.get(guild_id):
            # 佇列空了 → 恢復之前被我們暫停的音樂
            self._resume_music(guild_id, voice_client)
            return

        # 音樂或別的東西還在播 → 先暫停再插播 TTS，播完恢復
        if voice_client.is_paused() and not self.we_paused.get(guild_id):
            # 別人手動暫停的東西 → 不介入，等原本的東西處理完（排隊待播）
            return
        if voice_client.is_playing() and not self.we_paused.get(guild_id):
            # 第一次插播：保存被暫停的原始音樂 player（還原時要換回去），並暫停它
            self.saved_players[guild_id] = voice_client._player
            voice_client.pause()
            self.we_paused[guild_id] = True

        filepath = self.queue[guild_id].pop(0)

        # 定義播放結束後要刪除音檔並檢查下一首的回呼函式
        def after_playing(error):
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass
            if error:
                print(f"TTS after 錯誤: {error}")
            # 因為 after 是跑在 thread，要透過 bot.loop 再跑一次 play_next
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

    def _resume_music(self, guild_id, voice_client):
        """TTS 播完、佇列空了，恢復之前被我們暫停的音樂"""
        if not self.we_paused.get(guild_id):
            return
        self.we_paused[guild_id] = False
        try:
            saved = self.saved_players.pop(guild_id, None)
            # 把 voice_client 的 player 換回原本的音樂 player（TTS 的 player 已結束）
            if saved is not None and saved is not voice_client._player:
                voice_client._player = saved
            if voice_client.is_paused():
                voice_client.resume()
        except Exception as e:
            print(f"恢復音樂失敗: {e}")


async def setup(bot):
    await bot.add_cog(TTSCog(bot))
