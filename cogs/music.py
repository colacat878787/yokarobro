import discord
from discord.ext import commands, tasks
import yt_dlp
import asyncio
import os
import time
import json
import re
from datetime import timedelta

# --- YTDL 配置 ---
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
    def __init__(self, source, *, data, volume=0.5, pitch=1.0, theater=False, requester=None):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')
        self.pitch = pitch
        self.theater = theater
        self.requester = requester
        self.start_time = time.time()
        self.original_url = data.get('webpage_url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, volume=0.5, pitch=1.0, theater=False, seek=0, requester=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        filters = []
        if theater: filters.append("extrastereo=m=2.5")
        if pitch != 1.0: filters.append(f"asetrate=48000*{pitch},atempo=1/{pitch}")
        
        af_string = f"-af \"{','.join(filters)}\"" if filters else ""
        ffmpeg_options = {
            'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {seek}',
            'options': f'-vn {af_string}'
        }

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, volume=volume, pitch=pitch, theater=theater, requester=requester)

# ── 持久化音樂控制面板 ──
class MusicControlView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary, custom_id="mus_prev", row=0)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🚧 洛洛的時光機正在研發中，暫時只能跳過喔！", ephemeral=True)

    @discord.ui.button(label="⏸️/▶️", style=discord.ButtonStyle.primary, custom_id="mus_pause", row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return await interaction.response.send_message("❌ 沒有正在播出的音樂。", ephemeral=True)
        if vc.is_paused(): vc.resume()
        else: vc.pause()
        await interaction.response.defer()

    @discord.ui.button(label="⏭️ 跳過", style=discord.ButtonStyle.primary, custom_id="mus_skip", row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
        await interaction.response.defer()

    @discord.ui.button(label="⏹️ 停止", style=discord.ButtonStyle.danger, custom_id="mus_stop", row=0)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            self.cog.queue[interaction.guild_id] = []
        await interaction.response.defer()

    @discord.ui.button(label="🔄 重置 Key", style=discord.ButtonStyle.secondary, custom_id="mus_reset", row=1)
    async def reset_pitch(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(interaction.guild_id)
        state['pitch'] = 1.0
        await self.cog.reload_current(interaction.guild)
        await interaction.response.defer()

    @discord.ui.button(label="🎬 杜比", style=discord.ButtonStyle.success, custom_id="mus_theater", row=1)
    async def dolby(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(interaction.guild_id)
        state['theater'] = not state['theater']
        await self.cog.reload_current(interaction.guild)
        await interaction.response.defer()

    @discord.ui.button(label="🔊+", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_vol_up")
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_vol(interaction, 0.1)

    @discord.ui.button(label="🔉-", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_vol_down")
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_vol(interaction, -0.1)

    async def _adjust_vol(self, interaction, change):
        vc = interaction.guild.voice_client
        state = self.cog.get_state(interaction.guild_id)
        state['volume'] = max(0.0, min(1.0, state['volume'] + change))
        if vc and vc.source: vc.source.volume = state['volume']
        await interaction.response.defer()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        mgmt = self.cog.bot.get_cog("ManagementCog")
        if mgmt and mgmt.is_blacklisted(str(interaction.user.id)):
            await interaction.response.send_message("❌ 黑名單中，無法操作。", ephemeral=True)
            return False
        if not interaction.user.voice or not interaction.guild.voice_client or \
           interaction.user.voice.channel.id != interaction.guild.voice_client.channel.id:
            await interaction.response.send_message("❌ 嘿！妳必須跟我待在同一個語音房裡！", ephemeral=True)
            return False
        return True

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {} # guild_id: list
        self.panels = {} # guild_id: message
        self.settings_file = "music_settings.json"
        self.states = self.load_settings()
        self.bot.add_view(MusicControlView(self))
        self.update_panel_task.start()

    def cog_unload(self):
        self.update_panel_task.cancel()

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return {int(k): v for k, v in json.load(f).items()}
            except: pass
        return {}

    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump({str(k): v for k, v in self.states.items()}, f)
        except: pass

    def get_state(self, guild_id):
        if guild_id not in self.states:
            self.states[guild_id] = {'volume': 0.5, 'pitch': 1.0, 'theater': False, 'current_url': None, 'elapsed': 0}
        return self.states[guild_id]

    # --- 進度條與面板更新 ---
    def create_progress_bar(self, current, total):
        if total == 0: return "[🔘▬▬▬▬▬▬▬▬▬▬]"
        percent = current / total
        bar_len = 10
        filled = int(percent * bar_len)
        bar = list("▬▬▬▬▬▬▬▬▬▬")
        if 0 <= filled < bar_len: bar[filled] = "🔘"
        elif filled >= bar_len: bar[-1] = "🔘"
        else: bar[0] = "🔘"
        return f"[{''.join(bar)}]"

    @tasks.loop(seconds=1)
    async def update_panel_task(self):
        for guild_id, message in list(self.panels.items()):
            guild = self.bot.get_guild(guild_id)
            if not guild or not guild.voice_client or not guild.voice_client.source:
                continue
            
            try:
                vc = guild.voice_client
                source = vc.source
                state = self.get_state(guild_id)
                
                # 計算時間
                elapsed = int(time.time() - source.start_time + state.get('elapsed', 0))
                if vc.is_paused(): elapsed = int(state.get('last_elapsed', elapsed))
                state['last_elapsed'] = elapsed

                # 構建 Embed
                embed = self.create_music_embed(guild_id, source, elapsed)
                await message.edit(embed=embed, view=MusicControlView(self))
            except Exception as e:
                print(f"Panel Update Error ({guild_id}): {e}")

    def create_music_embed(self, guild_id, source, elapsed):
        state = self.get_state(guild_id)
        total = source.duration
        
        embed = discord.Embed(title=f"🎶 正在播放：{source.title}", color=0xed4245)
        if hasattr(source, 'thumbnail') and source.thumbnail: 
            embed.set_image(url=source.thumbnail)
        
        # 進度條
        bar = self.create_progress_bar(elapsed, total)
        time_str = f"`{str(timedelta(seconds=elapsed)).split('.')[0]} / {str(timedelta(seconds=total)).split('.')[0]}`"
        
        embed.description = f"{bar} {time_str}\n\n👤 **點歌者**：{source.requester.mention if source.requester else '未知'}"
        
        # 待播清單
        q = self.queue.get(guild_id, [])
        if q:
            q_list = "\n".join([f"**{i+1}.** {s.title}" for i, s in enumerate(q[:3])])
            if len(q) > 3: q_list += f"\n*...以及其他 {len(q)-3} 首歌曲*"
            embed.add_field(name="📜 待播清單", value=q_list, inline=False)
        else:
            embed.add_field(name="📜 待播清單", value="目前沒有下一首歌曲，快來點歌吧！", inline=False)

        # 狀態
        status = f"🔊 {int(state['volume']*100)}% | 🎵 {state['pitch']:.2f}x | 🎬 {'杜比 ON' if state['theater'] else '杜比 OFF'}"
        embed.set_footer(text=f"Yokaro Music Theater | {status}")
        return embed

    async def reload_current(self, guild):
        vc = guild.voice_client
        if not vc or not vc.source: return
        state = self.get_state(guild.id)
        if not state['current_url']: return

        current_elapsed = time.time() - vc.source.start_time + state['elapsed']
        try:
            new_source = await YTDLSource.from_url(
                state['current_url'], loop=self.bot.loop, 
                stream=not state['current_url'].startswith("temp/"),
                volume=state['volume'], pitch=state['pitch'], 
                theater=state['theater'], seek=int(current_elapsed), requester=vc.source.requester
            )
            new_source.start_time = time.time()
            state['elapsed'] = current_elapsed
            vc.source = new_source
            self.save_settings()
        except: pass

    # --- Spotify 跨平台解析器 (專業版 & 修復 DRM) ---
    async def resolve_spotify(self, ctx, url):
        async with ctx.typing():
            tracks = []
            
            # 優先嘗試：使用 spotify-dlp (專業版引擎)
            try:
                # 呼叫 spotify-dlp 指令抓取 metadata
                # 改用 python -m spotify_dlp 避免路徑問題
                import sys
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, '-m', 'spotify_dlp', '--get-title', url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                if proc.returncode == 0 and stdout:
                    output = stdout.decode().strip()
                    tracks = [line.strip() for line in output.splitlines() if line.strip()]
                    print(f"✅ Spotify-DLP 成功抓取 {len(tracks)} 首歌曲")
            except Exception as e:
                print(f"⚠️ Spotify-DLP 暫不可用，切換至爬蟲模式: {e}")

            # 次要嘗試：如果上面失敗，使用原本的 aiohttp 爬蟲模式
            if not tracks:
                try:
                    async with aiohttp.ClientSession() as session:
                        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                        async with session.get(url, headers=headers) as resp:
                            if resp.status == 200:
                                html = await resp.text()
                                title_match = re.search(r'<meta property="og:title" content="(.*?)"', html)
                                desc_match = re.search(r'<meta property="og:description" content="(.*?)"', html)
                                if title_match:
                                    raw_title = title_match.group(1)
                                    raw_desc = desc_match.group(1) if desc_match else ""
                                    artist = raw_desc.split('·')[0].strip() if '·' in raw_desc else raw_desc
                                    tracks = [f"{raw_title} {artist}"]
                except: pass

            if not tracks:
                return await ctx.send("❌ 洛洛盡力了，但暫時解析不了這個音樂連結喔！")

            # 開始處理搜尋與播放
            added_count = 0
            for query in tracks:
                try:
                    state = self.get_state(ctx.guild.id)
                    player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True, 
                                                     volume=state['volume'], pitch=state['pitch'], 
                                                     theater=state['theater'], requester=ctx.author)
                    if ctx.voice_client.is_playing():
                        if ctx.guild.id not in self.queue: self.queue[ctx.guild.id] = []
                        self.queue[ctx.guild.id].append(player)
                    else:
                        self._play_song(ctx, player)
                    added_count += 1
                except: continue
            
            if added_count > 1:
                await ctx.send(f"✅ 已透過核心引擎解析 Spotify，成功加入了 **{added_count}** 首歌！🐾")
            elif added_count == 1 and "open.spotify.com" in ctx.message.content:
                # 單曲不需要重複發送訊息，_play_song 已經發過面板了
                pass

    @commands.command(name='play', aliases=['播放', '播'])
    async def play(self, ctx, *, search):
        if not ctx.voice_client:
            if not ctx.author.voice: return await ctx.send("嗷～你沒在語音頻道耶！")
            await ctx.author.voice.channel.connect(timeout=60.0, reconnect=True)

        if "open.spotify.com" in search:
            return await self.resolve_spotify(ctx, search)
            
        async with ctx.typing():
            try:
                state = self.get_state(ctx.guild.id)
                player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True, 
                                                 volume=state['volume'], pitch=state['pitch'], 
                                                 theater=state['theater'], requester=ctx.author)
                
                if ctx.voice_client.is_playing():
                    gid = ctx.guild.id
                    if gid not in self.queue: self.queue[gid] = []
                    self.queue[gid].append(player)
                    await ctx.send(f"✅ **{player.title}** 已加入播放清單")
                else:
                    self._play_song(ctx, player)
            except Exception as e: await ctx.send(f"❌ 播放失敗: {e}")

    def _play_song(self, ctx, player):
        state = self.get_state(ctx.guild.id)
        state['current_url'] = player.original_url or player.url
        state['elapsed'] = 0
        state['last_elapsed'] = 0
        player.start_time = time.time()
        ctx.voice_client.play(player, after=lambda e: self.play_next(ctx))
        
        # 發送面板
        asyncio.run_coroutine_threadsafe(self.send_panel(ctx, player), self.bot.loop)

    async def send_panel(self, ctx, player):
        embed = self.create_music_embed(ctx.guild.id, player, 0)
        view = MusicControlView(self)
        msg = await ctx.send(embed=embed, view=view)
        # 如果舊的有面板，可以嘗試刪除 (可選)
        self.panels[ctx.guild.id] = msg

    def play_next(self, ctx):
        gid = ctx.guild.id
        if gid in self.queue and self.queue[gid] and ctx.voice_client:
            player = self.queue[gid].pop(0)
            self._play_song(ctx, player)
        else:
            if gid in self.panels:
                # 播放結束，清除面板
                self.panels.pop(gid)

    @commands.command(name='skip', aliases=['跳過'])
    async def skip(self, ctx):
        if ctx.voice_client:
            ctx.voice_client.stop()
            await ctx.send("⏩ 已跳過當前歌曲！")

    @commands.command(name='stop', aliases=['停止', '斷開', '下班'])
    async def stop(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.queue[ctx.guild.id] = []
            if ctx.guild.id in self.panels: self.panels.pop(ctx.guild.id)
            await ctx.send("🛑 已停止播放並清空清單。")

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
