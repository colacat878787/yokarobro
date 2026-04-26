import discord
from discord.ext import commands, tasks
import asyncio
import yt_dlp
import os
import json
import time
import re
import aiohttp
import random
from datetime import timedelta

# ── 音訊引擎設定 ──
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

RICKROLL_KEYWORDS = [
    "never gonna give you up", "rickroll", "rick roll", "nevergonnagiveyouup",
    "rickrolled", "rick rolling", "never gonna give u up"
]

def is_rickroll(title):
    if not title: return False
    clean_title = title.lower().replace(" ", "")
    for kw in RICKROLL_KEYWORDS:
        if kw.replace(" ", "") in clean_title:
            return True
    return False

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, pitch=1.0, theater=False, requester=None):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')
        self.requester = requester
        self.start_time = time.time()
        self.original_url = data.get('webpage_url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, volume=0.5, pitch=1.0, theater=False, spatial=False, agc=True, seek=0, requester=None):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            raise Exception(f"無法獲取影片資訊: {e}")
            
        if 'entries' in data: data = data['entries'][0]

        headers = data.get('http_headers', {})
        header_str = "".join([f"{k}: {v}\r\n" for k, v in headers.items()])

        filters = []
        if theater: filters.append("extrastereo=m=2.5")
        if spatial: filters.append("apulsator=hz=0.125")
        if agc: filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        if pitch != 1.0: filters.append(f"asetrate=48000*{pitch},atempo=1/{pitch}")
        
        af_string = f"-af \"{','.join(filters)}\"" if filters else ""
        opts = {
            'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {seek}',
            'options': f'-vn {af_string}'
        }
        if header_str: opts['before_options'] += f' -headers "{header_str}"'

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **opts), data=data, volume=volume, pitch=pitch, theater=theater, requester=requester)

# ── 搜尋選單 ──
class MusicSelectView(discord.ui.View):
    def __init__(self, cog, results, requester):
        super().__init__(timeout=60)
        self.cog, self.results, self.requester = cog, results, requester
        select = discord.ui.Select(placeholder="🎯 選一首你想聽的歌吧！")
        for i, res in enumerate(results[:5]):
            select.add_option(label=res.get('title', '未知')[:100], value=str(i), description=f"時長: {timedelta(seconds=res.get('duration',0))}", emoji="🎵")
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id: return await interaction.response.send_message("❌ 非本人搜尋。", ephemeral=True)
        await interaction.response.defer()
        url = self.results[int(interaction.data['values'][0])].get('webpage_url')
        ctx = await self.cog.bot.get_context(interaction.message)
        ctx.author = self.requester
        await self.cog.play(ctx, search=url)
        await interaction.delete_original_response()

# ── 劇院控制面板 ──
class MusicControlView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="🔁", style=discord.ButtonStyle.secondary, custom_id="mus_loop", row=0)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(interaction.guild_id)
        modes = [None, 'single', 'queue']
        state['loop'] = modes[(modes.index(state.get('loop')) + 1) % 3]
        button.label = {None: "🔁", 'single': "🔂", 'queue': "🔁 [Q]"}[state['loop']]
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏸️", style=discord.ButtonStyle.primary, custom_id="mus_pause", row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return
        if vc.is_paused(): vc.resume(); button.label = "⏸️"
        else: vc.pause(); button.label = "▶️"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.primary, custom_id="mus_skip", row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client: interaction.guild.voice_client.stop()
        await interaction.response.defer()

    @discord.ui.button(label="⏹️ 停止", style=discord.ButtonStyle.danger, custom_id="mus_stop", row=0)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            self.cog.queue[interaction.guild_id] = []
        await interaction.response.defer()

    @discord.ui.button(label="🔉", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_vol_down")
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_vol(interaction, -0.1)

    @discord.ui.button(label="🔊", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_vol_up")
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_vol(interaction, 0.1)

    @discord.ui.button(label="🎹-", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_pitch_down")
    async def pitch_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_pitch(interaction, -0.05)

    @discord.ui.button(label="🎹+", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_pitch_up")
    async def pitch_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_pitch(interaction, 0.05)

    @discord.ui.button(label="🎲 隨機", style=discord.ButtonStyle.secondary, custom_id="mus_shuffle", row=2)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        if gid in self.cog.queue and self.cog.queue[gid]:
            random.shuffle(self.cog.queue[gid])
            await interaction.response.send_message("🎲 隊列已打亂！", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 隊列是空的喔！", ephemeral=True)

    @discord.ui.button(label="🗑️ 清空", style=discord.ButtonStyle.secondary, custom_id="mus_clear", row=2)
    async def clear_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.queue[interaction.guild_id] = []
        await interaction.response.send_message("🧹 播放清單已清空！", ephemeral=True)

    @discord.ui.button(label="📜 列表", style=discord.ButtonStyle.secondary, custom_id="mus_queue_view", row=2)
    async def view_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        ctx = await self.cog.bot.get_context(interaction.message)
        await self.cog.queue_cmd(ctx)
        await interaction.response.defer()

    @discord.ui.button(label="📻 續播: ON", style=discord.ButtonStyle.success, custom_id="mus_autoplay", row=3)
    async def toggle_autoplay(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(interaction.guild_id)
        state['autoplay'] = not state.get('autoplay', True)
        button.label = f"📻 續播: {'ON' if state['autoplay'] else 'OFF'}"
        button.style = discord.ButtonStyle.success if state['autoplay'] else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="🎬 杜比: OFF", style=discord.ButtonStyle.secondary, custom_id="mus_dolby", row=3)
    async def dolby(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(interaction.guild_id)
        state['theater'] = not state['theater']
        button.label = f"🎬 杜比: {'ON' if state['theater'] else 'OFF'}"
        button.style = discord.ButtonStyle.success if state['theater'] else discord.ButtonStyle.secondary
        await self.cog.reload_current(interaction.guild)
        await interaction.response.edit_message(view=self)

    async def _adjust_vol(self, interaction, change):
        vc = interaction.guild.voice_client
        state = self.cog.get_state(interaction.guild_id)
        state['volume'] = max(0.0, min(1.0, state['volume'] + change))
        if vc and vc.source: vc.source.volume = state['volume']
        await interaction.response.defer()

    async def _adjust_pitch(self, interaction, change):
        state = self.cog.get_state(interaction.guild_id)
        state['pitch'] = max(0.5, min(2.0, state['pitch'] + change))
        await self.cog.reload_current(interaction.guild)
        await interaction.response.defer()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue, self.panels = {}, {}
        self.states = {}
        self.history_file = "music_history.json"
        self.update_panel_task.start()

    def cog_unload(self):
        self.update_panel_task.cancel()

    def log_history(self, user_id, title):
        try:
            history = {}
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            uid = str(user_id)
            if uid not in history: history[uid] = {}
            history[uid][title] = history[uid].get(title, 0) + 1
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
        except: pass

    def get_state(self, gid):
        if gid not in self.states: self.states[gid] = {'volume': 0.5, 'pitch': 1.0, 'theater': False, 'spatial': False, 'loop': None, '247': False, 'antirickroll': True, 'autoplay': True}
        return self.states[gid]

    @tasks.loop(seconds=1)
    async def update_panel_task(self):
        for gid, msg in list(self.panels.items()):
            try:
                guild = self.bot.get_guild(gid)
                if not guild or not guild.voice_client or not guild.voice_client.source: continue
                vc, source, state = guild.voice_client, guild.voice_client.source, self.get_state(gid)
                elapsed = int(time.time() - source.start_time + state.get('elapsed', 0))
                if vc.is_paused(): elapsed = int(state.get('last_elapsed', elapsed))
                state['last_elapsed'] = elapsed
                await msg.edit(embed=self.create_music_embed(gid, source, elapsed))
            except: pass

    def create_music_embed(self, gid, source, elapsed):
        state = self.get_state(gid)
        vol = state['volume']
        vol_icon = "🔇" if vol == 0 else "🔈" if vol < 0.4 else "🔉" if vol < 0.7 else "🔊"
        embed = discord.Embed(title=f"🎶 正在播放：{source.title}", color=0xed4245)
        if source.thumbnail: embed.set_image(url=source.thumbnail)
        percent = elapsed / source.duration if source.duration > 0 else 0
        bar = list("▬▬▬▬▬▬▬▬▬▬")
        bar[min(int(percent * 10), 9)] = "🔘"
        
        status_line = f"🎬 杜比: {'✅' if state['theater'] else '❌'} | 📻 續播: {'✅' if state.get('autoplay', True) else '❌'}"
        embed.description = f"[{''.join(bar)}] `{timedelta(seconds=elapsed)} / {timedelta(seconds=source.duration)}`\n\n{status_line}\n\n👤 **點歌者**：{source.requester.mention if source.requester else '未知'}"
        embed.set_footer(text=f"Yokaro Theater | {vol_icon} {int(vol*100)}% | 🎹 {state['pitch']:.2f}x", icon_url=source.requester.display_avatar.url if source.requester else None)
        return embed

    @commands.command(name='play', aliases=['播放', '播', 'p'])
    async def play(self, ctx, *, search):
        if not ctx.voice_client:
            if not ctx.author.voice: return await ctx.send("妳要先加入頻道！")
            await ctx.author.voice.channel.connect()

        if "open.spotify.com" in search: return await self.resolve_spotify(ctx, search)
        
        async with ctx.typing():
            try:
                state = self.get_state(ctx.guild.id)
                if not search.startswith("http"):
                    data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{search}", download=False))
                    results = [e for e in data['entries'] if not (state['antirickroll'] and is_rickroll(e.get('title')))]
                    if not results: return await ctx.send("🚫 **偵測到 Rickroll，已攔截！**")
                    return await ctx.send(f"🔍 搜尋結果：", view=MusicSelectView(self, results, ctx.author))

                # 網址檢查
                info = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
                if state['antirickroll'] and is_rickroll(info.get('title')):
                    return await ctx.send("🚫 **警告：偵測到 Rickroll 攻擊！**")

                player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True, volume=state['volume'], pitch=state['pitch'], theater=state['theater'], requester=ctx.author)
                if ctx.voice_client.is_playing():
                    gid = ctx.guild.id
                    if gid not in self.queue: self.queue[gid] = []
                    self.queue[gid].append(player)
                    await ctx.send(f"✅ **{player.title}** 已加入隊列！")
                else: self._play_song(ctx, player)
            except Exception as e: await ctx.send(f"❌ 錯誤: {e}")

    def _play_song(self, ctx, player):
        state = self.get_state(ctx.guild.id)
        state['current_url'], state['elapsed'] = player.original_url or player.url, 0
        player.start_time = time.time()
        self.log_history(player.requester.id if player.requester else 0, player.title)
        ctx.voice_client.play(player, after=lambda e: self.play_next(ctx))
        asyncio.run_coroutine_threadsafe(self.send_panel(ctx, player), self.bot.loop)

    async def send_panel(self, ctx, player):
        msg = await ctx.send(embed=self.create_music_embed(ctx.guild.id, player, 0), view=MusicControlView(self))
        self.panels[ctx.guild.id] = msg

    def play_next(self, ctx):
        gid = ctx.guild.id
        state = self.get_state(gid)
        if state['loop'] == 'single':
            asyncio.run_coroutine_threadsafe(self.reload_current_raw(ctx), self.bot.loop)
            return
        if gid in self.queue and self.queue[gid]:
            player = self.queue[gid].pop(0)
            if state['loop'] == 'queue': self.queue[gid].append(player)
            self._play_song(ctx, player)
        else:
            if state.get('autoplay', True):
                asyncio.run_coroutine_threadsafe(self.autoplay(ctx), self.bot.loop)

    async def autoplay(self, ctx):
        state = self.get_state(ctx.guild.id)
        if not state.get('current_url'): return
        try:
            data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(state['current_url'], download=False))
            if 'related_videos' in data:
                url = f"https://www.youtube.com/watch?v={data['related_videos'][0]['id']}"
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True, requester=self.bot.user)
                await ctx.send(f"📻 AI 自動續播：**{player.title}**")
                self._play_song(ctx, player)
        except: pass

    async def reload_current_raw(self, ctx):
        state = self.get_state(ctx.guild.id)
        player = await YTDLSource.from_url(state['current_url'], loop=self.bot.loop, stream=True, requester=ctx.author)
        self._play_song(ctx, player)

    async def reload_current(self, guild):
        vc = guild.voice_client
        if not vc or not vc.source: return
        state = self.get_state(guild.id)
        # 計算目前進度，實現無縫接軌
        elapsed = int(time.time() - vc.source.start_time + state.get('elapsed', 0))
        state['elapsed'] = elapsed # 儲存進度以供下一次偏移
        
        player = await YTDLSource.from_url(state['current_url'], loop=self.bot.loop, stream=True, 
                                         volume=state['volume'], pitch=state['pitch'], 
                                         theater=state['theater'], seek=elapsed, # 關鍵：傳入當前秒數
                                         requester=vc.source.requester)
        vc.source = player
        player.start_time = time.time() # 重設起始時間

    async def resolve_spotify(self, ctx, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://open.spotify.com/oembed?url={url}") as r:
                if r.status == 200:
                    data = await r.json()
                    await self.play(ctx, search=f"{data['title']} {data['provider_name']}")

    @commands.command(name='queue', aliases=['q', '列表', '清單'])
    async def queue_cmd(self, ctx):
        q = self.queue.get(ctx.guild.id, [])
        embed = discord.Embed(title="📜 播放清單", description="\n".join([f"**{i+1}.** {p.title}" for i, p in enumerate(q[:10])]) or "隊列是空的！")
        await ctx.send(embed=embed)

    @commands.command(name='recap', aliases=['回顧', '紀錄'])
    async def recap(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        if not os.path.exists(self.history_file): return await ctx.send("📊 無數據。")
        with open(self.history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        uid = str(target.id)
        if uid not in history: return await ctx.send(f"📊 {target.display_name} 無點歌紀錄。")
        user_data = history[uid]
        sorted_songs = sorted(user_data.items(), key=lambda x: x[1], reverse=True)
        top_songs = "\n".join([f"🎵 **{s[0]}** ({s[1]} 次)" for s in sorted_songs[:5]])
        embed = discord.Embed(title=f"📊 {target.display_name} 的音樂回顧", description=top_songs or "無", color=0x9b59b6)
        await ctx.send(embed=embed)

    @commands.command(name='antirickroll')
    async def toggle_antirickroll(self, ctx, mode: str = None):
        state = self.get_state(ctx.guild.id)
        state['antirickroll'] = mode.lower() == "on" if mode else not state['antirickroll']
        await ctx.send(f"🛡️ 反 Rickroll 已 {'開啟' if state['antirickroll'] else '關閉'}！")

    @commands.command(name='247')
    @commands.has_permissions(administrator=True)
    async def toggle_247(self, ctx):
        state = self.get_state(ctx.guild.id)
        state['247'] = not state.get('247', False)
        await ctx.send(f"🌌 24/7 模式已 {'開啟' if state['247'] else '關閉'}！")

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
