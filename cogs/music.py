import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
import time
import json

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

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, pitch=1.0, theater=False):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.pitch = pitch
        self.theater = theater
        self.start_time = time.time() # 记录开始时间

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, volume=0.5, pitch=1.0, theater=False, seek=0):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        # --- 構建動態濾鏡 ---
        filters = []
        if theater:
            # 劇院模式: 使用相容性最高的 extrastereo 濾鏡模擬空間感
            filters.append("extrastereo=m=2.5")
        
        if pitch != 1.0:
            # 升降 Key: 調整取樣率與速度校正
            filters.append(f"asetrate=48000*{pitch},atempo=1/{pitch}")
        
        af_string = f"-af \"{','.join(filters)}\"" if filters else ""
        
        ffmpeg_options = {
            'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {seek}',
            'options': f'-vn {af_string}'
        }

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, volume=volume, pitch=pitch, theater=theater)

# ── 持久化音樂控制面板 ──
class MusicControlView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="⏬ 降Key", style=discord.ButtonStyle.secondary, custom_id="mus_key_down", row=0)
    async def key_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_pitch(interaction, -0.05)

    @discord.ui.button(label="🔄 重置", style=discord.ButtonStyle.secondary, custom_id="mus_reset", row=0)
    async def reset_pitch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        state = self.cog.get_state(interaction.guild_id)
        state['pitch'] = 1.0
        await self.cog.reload_current(interaction.guild)
        await interaction.edit_original_response(content="🎵 音調已重置為 1.0x (正常音速)！")

    @discord.ui.button(label="⏫ 升Key", style=discord.ButtonStyle.secondary, custom_id="mus_key_up", row=0)
    async def key_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_pitch(interaction, 0.05)

    @discord.ui.button(label="🎧 杜比環繞", style=discord.ButtonStyle.success, custom_id="mus_theater", row=0)
    async def dolby(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        state = self.cog.get_state(guild_id)
        state['theater'] = not state['theater']
        mode = "開啟" if state['theater'] else "關閉"
        await self.cog.reload_current(interaction.guild)
        await interaction.edit_original_response(content=f"🎬 劇院杜比模式已 {mode}！")

    @discord.ui.button(label="⏩ 跳過", style=discord.ButtonStyle.primary, custom_id="mus_skip", row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.edit_original_response(content="⏩ 已跳過當前歌曲！")

    @discord.ui.button(label="⏸️ 暫停/繼續", style=discord.ButtonStyle.primary, custom_id="mus_pause", row=1)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.edit_original_response(content="❌ 洛洛目前沒有在唱歌喔！")
            
        if vc.is_paused():
            vc.resume()
            await interaction.edit_original_response(content="▶️ 指令收到！繼續播放～嗷嗚！")
        else:
            vc.pause()
            await interaction.edit_original_response(content="⏸️ 洛洛先休息喝口水，暫停播放囉。")

    @discord.ui.button(label="⏹️ 停止", style=discord.ButtonStyle.danger, custom_id="mus_stop", row=1)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            self.cog.queue[interaction.guild_id] = []
            await interaction.edit_original_response(content="🛑 已停止播放並清空清單。")

    @discord.ui.button(label="🔉 音量-10", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_vol_down")
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_vol(interaction, -0.1)

    @discord.ui.button(label="🔊 音量+10", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_vol_up")
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_vol(interaction, 0.1)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # --- 唯一機密封印 ---
        # 只有親爸爸 (擁有者) 可以操控此面板
        if interaction.user.id != 1113353915010920452:
            await interaction.response.send_message("⚠️ 嗷！這是**機密控制面板**，只有親爸爸可以碰喔！🐾", ephemeral=True)
            return False
        return True

    async def _adjust_pitch(self, interaction, change):
        await interaction.response.defer(ephemeral=True)
        state = self.cog.get_state(interaction.guild_id)
        state['pitch'] = max(0.5, min(2.0, state['pitch'] + change))
        await self.cog.reload_current(interaction.guild)
        await interaction.edit_original_response(content=f"🎵 音調已調整至: {state['pitch']:.2f}x")

    async def _adjust_vol(self, interaction, change):
        await interaction.response.defer(ephemeral=True)
        vc = interaction.guild.voice_client
        state = self.cog.get_state(interaction.guild_id)
        state['volume'] = max(0.0, state['volume'] + change)
        if vc and vc.source:
            vc.source.volume = state['volume']
        await interaction.edit_original_response(content=f"🔊 音量已調整至: {int(state['volume']*100)}%")

    async def on_error(self, interaction, error, item):
        print(f"MusicControl Error: {error}")

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {} # guild_id: list
        self.settings_file = "music_settings.json"
        self.states = self.load_settings()
        # 註冊持久化面板
        self.bot.add_view(MusicControlView(self))

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 将 key 转为 int 以匹配 guild_id
                    return {int(k): v for k, v in data.items()}
            except Exception as e:
                print(f"讀取音樂設定失敗: {e}")
        return {}

    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                # 将 key 转为 str 才能存储
                data = {str(k): v for k, v in self.states.items()}
                json.dump(data, f)
        except Exception as e:
            print(f"儲存音樂設定失敗: {e}")

    def get_state(self, guild_id):
        if guild_id not in self.states:
            self.states[guild_id] = {'volume': 0.5, 'pitch': 1.0, 'theater': False, 'current_url': None, 'elapsed': 0}
        return self.states[guild_id]

    async def reload_current(self, guild):
        """重新加載當前歌曲以套用濾鏡"""
        vc = guild.voice_client
        if not vc or not vc.source:
            return
        
        state = self.get_state(guild.id)
        if not state['current_url']:
            return

        # 計算已播放時間
        current_elapsed = time.time() - vc.source.start_time + state['elapsed']
        
        try:
            new_source = await YTDLSource.from_url(
                state['current_url'], 
                loop=self.bot.loop, 
                stream=not state['current_url'].startswith("temp/"), # 如果是本機檔案不使用 stream
                volume=state['volume'],
                pitch=state['pitch'],
                theater=state['theater'],
                seek=int(current_elapsed)
            )
            new_source.start_time = time.time()
            state['elapsed'] = current_elapsed
            vc.source = new_source
            self.save_settings() # 每次變更都存檔
        except Exception as e:
            print(f"Reload failed: {e}")

    @commands.command(name='movie', aliases=['電影', '影片'])
    async def movie(self, ctx):
        """上傳 MP4 影片，洛洛幫你廣播劇院級音軌"""
        if not ctx.message.attachments:
            return await ctx.send("❓ 請上傳一個 `.mp4` 影片檔案，我會為大家廣播劇院特效音軌喔！")
        
        attachment = ctx.message.attachments[0]
        if not attachment.filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
            return await ctx.send("❌ 洛洛目前只收影片檔案檔案喔 (mp4, mkv, mov 等)！")

        async with ctx.typing():
            if not ctx.voice_client:
                if not ctx.author.voice:
                    return await ctx.send("嗷～你沒在語音頻道耶！")
                await ctx.author.voice.channel.connect(timeout=60.0, reconnect=True)

            # 確保暫存目錄存在
            if not os.path.exists("temp"): os.mkdir("temp")
            file_path = f"temp/{attachment.filename}"
            await attachment.save(file_path)

            state = self.get_state(ctx.guild.id)
            state['theater'] = True # 電影預設開啟劇院模式
            
            player = await YTDLSource.from_url(
                file_path, 
                loop=self.bot.loop, 
                stream=False, # 本機播放
                volume=state['volume'],
                pitch=state['pitch'],
                theater=state['theater']
            )

            # 更新狀態
            state['current_url'] = file_path
            
            if ctx.voice_client.is_playing():
                if ctx.guild.id not in self.queue: self.queue[ctx.guild.id] = []
                self.queue[ctx.guild.id].append(player)
                await ctx.send(f"🎬 影片 **{attachment.filename}** 已加入劇院播放清單！")
            else:
                self._play_song(ctx, player)
                embed = discord.Embed(title="🎬 星空電影院模式：ON", color=0xe91e63)
                embed.description = f"正在播映：**{attachment.filename}**\n🔊 杜比劇院濾鏡已自動同步開啟！"
                embed.set_footer(text="提示：請大家自行打開影片檔與洛洛的音軌同步喔！")
                await ctx.send(embed=embed)
            
            self.save_settings()

    @commands.command(name='musicpanel', aliases=['音樂面板', 'mp'])
    async def music_panel(self, ctx):
        """開啟音樂控制面板"""
        embed = discord.Embed(title="🎵 Yokaro 音樂劇院控制中心", color=0x9b59b6)
        embed.description = "您可以在下方即時調整音量、升降 Key 或開啟杜比環繞效果。"
        embed.add_field(name="🎧 劇院模式", value="使用 FFmpeg 分離聲道營造環繞感", inline=False)
        embed.set_footer(text="洛洛劇院系統 | 支援 3D 環繞與動態調音")
        view = MusicControlView(self)
        await ctx.send(embed=embed, view=view)

    @commands.command(name='play', aliases=['播放', '播'])
    async def play(self, ctx, *, search):
        async with ctx.typing():
            try:
                if not ctx.voice_client:
                    if not ctx.author.voice:
                        return await ctx.send("嗷～你沒在語音頻道耶！")
                    await ctx.author.voice.channel.connect(timeout=60.0, reconnect=True)
                
                state = self.get_state(ctx.guild.id)
                player = await YTDLSource.from_url(
                    search, 
                    loop=self.bot.loop, 
                    stream=True, 
                    volume=state['volume'],
                    pitch=state['pitch'],
                    theater=state['theater']
                )
                
                gid = ctx.guild.id
                if gid not in self.queue: self.queue[gid] = []

                if ctx.voice_client.is_playing():
                    self.queue[gid].append(player)
                    await ctx.send(f"✅ **{player.title}** 已加入播放清單")
                else:
                    self._play_song(ctx, player)
                    await ctx.send(f"🎶 正在播放: **{player.title}**")
            except Exception as e:
                await ctx.send(f"❌ 播放失敗: {e}")

    def _play_song(self, ctx, player):
        state = self.get_state(ctx.guild.id)
        state['current_url'] = player.url
        state['elapsed'] = 0
        player.start_time = time.time()
        ctx.voice_client.play(player, after=lambda e: self.play_next(ctx))

    def play_next(self, ctx):
        gid = ctx.guild.id
        if gid in self.queue and self.queue[gid] and ctx.voice_client:
            player = self.queue[gid].pop(0)
            self._play_song(ctx, player)
            asyncio.run_coroutine_threadsafe(ctx.send(f"⏭️ 下一首: **{player.title}**"), self.bot.loop)

    @commands.command(name='skip', aliases=['跳過'])
    async def skip(self, ctx):
        if ctx.voice_client:
            ctx.voice_client.stop()
            await ctx.send("⏩ 已跳過當前歌曲！")

    @commands.command(name='stop', aliases=['停止', '斷開', '下班'])
    async def stop(self, ctx):
        """停止播放、清空隊列並離開語音頻道"""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            gid = ctx.guild.id
            self.queue[gid] = []
            await ctx.send("🛑 已停止播放並清空清單，洛洛休息去囉！嗷～")
        else:
            await ctx.send("❓ 洛洛現在沒有在唱歌喔！")

    @commands.command(name='volume', aliases=['音量'])
    async def volume(self, ctx, vol: int):
        """調整音量 (如: !volume 100)"""
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = vol / 100
            state = self.get_state(ctx.guild.id)
            state['volume'] = vol / 100
            await ctx.send(f"🔊 音量已設定為: {vol}%")

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
