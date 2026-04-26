import discord
from discord.ext import commands, tasks
import yt_dlp
import asyncio
import os
import time
import json
import re
from datetime import timedelta
import aiohttp
import random

# --- YTDL 設定 ---
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
    def __init__(self, source, *, data, volume=0.5, pitch=1.0, theater=True, exciter=True, bass=True, requester=None):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')
        self.pitch = pitch
        self.theater = theater
        self.exciter = exciter
        self.bass = bass
        self.requester = requester
        self.start_time = time.time()
        self.original_url = data.get('webpage_url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, volume=0.5, pitch=1.0, theater=True, exciter=True, bass=True, seek=0, requester=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        headers = data.get('http_headers', {})
        header_str = "".join([f"{k}: {v}\r\n" for k, v in headers.items()])

        filters = []
        if theater: filters.append("extrastereo=m=2.5")
        if exciter: filters.append("highpass=f=200, treble=g=5")
        if bass: filters.append("bass=g=10:f=110:w=0.6")
        if pitch != 1.0: filters.append(f"asetrate=48000*{pitch},atempo=1/{pitch}")
        if not filters: filters.append("loudnorm")
        
        af_string = f"-af \"{','.join(filters)}\"" if filters else ""
        ffmpeg_options = {
            'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {seek}',
            'options': f'-vn {af_string}'
        }
        
        if header_str:
            ffmpeg_options['before_options'] += f' -headers "{header_str}"'

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, volume=volume, pitch=pitch, theater=theater, exciter=exciter, bass=bass, requester=requester)

class MusicControlView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="上一首", style=discord.ButtonStyle.secondary, custom_id="mus_prev", row=0)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏮️ 功能還在開發中，請先享受現在的音樂！", ephemeral=True)

    @discord.ui.button(label="暫停/播放", style=discord.ButtonStyle.primary, custom_id="mus_pause", row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return await interaction.response.send_message("❌ 沒有在播放音樂。", ephemeral=True)
        if vc.is_paused(): vc.resume()
        else: vc.pause()
        await interaction.response.defer()

    @discord.ui.button(label="⏭️ 跳過", style=discord.ButtonStyle.primary, custom_id="mus_skip", row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
        await interaction.response.defer()

    @discord.ui.button(label="🛑 停止", style=discord.ButtonStyle.danger, custom_id="mus_stop", row=0)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            self.cog.queue[interaction.guild_id] = []
        await interaction.response.defer()

    @discord.ui.button(label="音量-", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_vol_down")
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_vol(interaction, -0.1)

    @discord.ui.button(label="音量+", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_vol_up")
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_vol(interaction, 0.1)

    @discord.ui.button(label="音調-", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_pitch_down")
    async def pitch_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_pitch(interaction, -0.05)

    @discord.ui.button(label="音調+", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_pitch_up")
    async def pitch_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_pitch(interaction, 0.05)

    @discord.ui.button(label="♻️ 重置", style=discord.ButtonStyle.secondary, custom_id="mus_reset", row=1)
    async def reset_pitch(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(interaction.guild_id)
        state['pitch'] = 1.0
        await self.cog.reload_current(interaction.guild)
        await interaction.response.defer()

    @discord.ui.button(label="🎬 杜比劇院 (Premium)", style=discord.ButtonStyle.success, custom_id="mus_theater", row=2)
    async def dolby(self, interaction: discord.Interaction, button: discord.ui.Button):
        kuji = self.cog.bot.get_cog("KujiCog")
        if not (kuji and kuji.is_premium(interaction.user.id)):
            return await interaction.response.send_message("💎 **杜比音效為 Premium 專屬功能！** 請去抽取一番賞解鎖！", ephemeral=True)
        state = self.cog.get_state(interaction.guild_id)
        state['theater'] = not state.get('theater', True)
        state['exciter'] = state['theater']
        state['bass'] = state['theater']
        await self.cog.reload_current(interaction.guild)
        await interaction.response.defer()

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
        mgmt = self.cog.bot.get_cog("ManagementCog")
        if mgmt and mgmt.is_blacklisted(str(interaction.user.id)):
            await interaction.response.send_message("❌ 您在黑名單中。", ephemeral=True)
            return False
        if not interaction.user.voice or not interaction.guild.voice_client or \
           interaction.user.voice.channel.id != interaction.guild.voice_client.channel.id:
            await interaction.response.send_message("❌ 您必須和我在同一個語音頻道。", ephemeral=True)
            return False
        return True

class MusicSelectView(discord.ui.View):
    def __init__(self, cog, results, requester):
        super().__init__(timeout=60)
        self.cog = cog
        self.results = results
        self.requester = requester
        
        select = discord.ui.Select(placeholder="🔍 請選擇您想要播放的歌曲", min_values=1, max_values=1)
        for i, res in enumerate(results):
            title = res.get('title', '未知')[:100]
            duration = str(timedelta(seconds=res.get('duration', 0)))
            select.add_option(
                label=title,
                value=str(i),
                description=f"長度: {duration} | 頻道: {res.get('uploader', '未知')[:50]}",
                emoji="🎶"
            )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            return await interaction.response.send_message("❌ 這是別人的點歌選單喔！", ephemeral=True)
            
        await interaction.response.defer()
        idx = int(interaction.data['values'][0])
        res = self.results[idx]
        url = res.get('webpage_url') or res.get('url')
        
        ctx = await self.cog.bot.get_context(interaction.message)
        ctx.author = self.requester 
        await self.cog.play(ctx, search=url)
        
        await interaction.delete_original_response()

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {} # guild_id: list
        self.panels = {} # guild_id: message
        self.settings_file = "music_settings.json"
        self.states = self.load_settings()
        self.bot.add_view(MusicControlView(self))
        self.history_file = "music_history.json"
        self.history = self._load_history()
        self.update_panel_task.start()

    def cog_unload(self):
        self.update_panel_task.cancel()

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f: 
                    data = json.load(f)
                    for k, v in list(data.items()):
                        if isinstance(v, dict):
                            new_list = []
                            for song, count in v.items():
                                if isinstance(count, int): new_list.extend([song] * count)
                                else: new_list.append(song)
                            data[k] = new_list
                        elif not isinstance(v, list):
                            data[k] = []
                    return data
            except: pass
        return {}

    def _save_history(self):
        with open(self.history_file, 'w', encoding='utf-8') as f: json.dump(self.history, f)

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
            self.states[guild_id] = {'volume': 0.5, 'pitch': 1.0, 'theater': True, 'exciter': True, 'bass': True, 'current_url': None, 'elapsed': 0, '247': False}
        return self.states[guild_id]

    def create_progress_bar(self, current, total):
        if total == 0: return "[▬▬▬▬▬▬▬▬▬🔘]"
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
                
                elapsed = int(time.time() - source.start_time + state.get('elapsed', 0))
                if vc.is_paused(): elapsed = int(state.get('last_elapsed', elapsed))
                state['last_elapsed'] = elapsed

                embed = self.create_music_embed(guild_id, source, elapsed)
                await message.edit(embed=embed, view=MusicControlView(self))
            except Exception as e:
                pass

    def create_music_embed(self, guild_id, source, elapsed):
        state = self.get_state(guild_id)
        total = source.duration
        
        embed = discord.Embed(title=f"🎶 正在播放：{source.title}", color=0xed4245)
        if hasattr(source, 'thumbnail') and source.thumbnail: 
            embed.set_image(url=source.thumbnail)
        
        bar = self.create_progress_bar(elapsed, total)
        time_str = f"`{str(timedelta(seconds=elapsed)).split('.')[0]} / {str(timedelta(seconds=total)).split('.')[0]}`"
        
        embed.description = f"{bar} {time_str}\n\n👤 **點歌者**：{source.requester.mention if source.requester else '未知'}"
        
        q = self.queue.get(guild_id, [])
        if q:
            q_list = ""
            for i, s in enumerate(q[:3]):
                if isinstance(s, dict) and s.get('type') == 'lazy':
                    title = s['query'].replace('ytsearch1:', '').replace('audio', '').strip()
                    q_list += f"**{i+1}.** {title[:40]} (載入中...)\n"
                else:
                    q_list += f"**{i+1}.** {s.title[:40]}\n"
            if len(q) > 3: q_list += f"\n*...以及其他 {len(q)-3} 首 (輸入 !queue 查看全部)*"
            embed.add_field(name="📜 播放清單", value=q_list, inline=False)
        else:
            embed.add_field(name="📜 播放清單", value="隊列是空的喔！快點歌吧！", inline=False)

        status = f"音量 {int(state['volume']*100)}% | 音調 {state['pitch']:.2f}x | 劇院 {'ON' if state.get('theater') else 'OFF'} | 續播 {'ON' if state.get('247') else 'OFF'}"
        embed.set_footer(text=f"Yokaro Music Theater | {status}")
        return embed

    async def reload_current(self, guild):
        vc = guild.voice_client
        if not vc or not vc.source: return
        state = self.get_state(guild.id)
        if not state['current_url']: return

        current_elapsed = time.time() - vc.source.start_time + state['elapsed']
        kuji = self.bot.get_cog("KujiCog")
        is_prem = kuji and vc.source.requester and kuji.is_premium(vc.source.requester.id)
        try:
            new_source = await YTDLSource.from_url(
                state['current_url'], loop=self.bot.loop, 
                stream=not state['current_url'].startswith("temp/"),
                volume=state['volume'], pitch=state['pitch'], 
                theater=is_prem and state.get('theater', True), 
                exciter=is_prem and state.get('exciter', True), 
                bass=is_prem and state.get('bass', True), 
                seek=int(current_elapsed), requester=vc.source.requester
            )
            new_source.start_time = time.time()
            state['elapsed'] = current_elapsed
            vc.source = new_source
            self.save_settings()
        except: pass

    async def resolve_spotify(self, ctx, url):
        async with ctx.typing():
            tracks = [] 
            try:
                import sys
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, '-m', 'yt_dlp', '--dump-json', '--flat-playlist', url,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0 and stdout:
                    for line in stdout.decode().splitlines():
                        try:
                            data = json.loads(line)
                            title = data.get('title')
                            uploader = data.get('uploader', '')
                            if title: tracks.append(f"{title} {uploader}")
                        except: continue
            except: pass

            if not tracks:
                try:
                    async with aiohttp.ClientSession() as session:
                        oembed_url = f"https://open.spotify.com/oembed?url={url}"
                        async with session.get(oembed_url) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                title = data.get('title')
                                artist = data.get('provider_name', '') 
                                if title:
                                    tracks = [f"{title} {artist}"]
                except: pass

            if not tracks:
                return await ctx.send("❌ 抱歉！洛洛無法解析這個 Spotify 連結。")

            added_count = 0
            if tracks:
                query = tracks.pop(0)
                state = self.get_state(ctx.guild.id)
                kuji = self.bot.get_cog("KujiCog")
                is_prem = kuji and kuji.is_premium(ctx.author.id)
                player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True, 
                                                 volume=state['volume'], pitch=state['pitch'], 
                                                 theater=is_prem and state.get('theater', True), 
                                                 exciter=is_prem and state.get('exciter', True), 
                                                 bass=is_prem and state.get('bass', True), 
                                                 requester=ctx.author)
                if ctx.voice_client.is_playing():
                    if ctx.guild.id not in self.queue: self.queue[ctx.guild.id] = []
                    self.queue[ctx.guild.id].append(player)
                else:
                    self._play_song(ctx, player)
                added_count += 1
            
            for query in tracks:
                if ctx.guild.id not in self.queue: self.queue[ctx.guild.id] = []
                self.queue[ctx.guild.id].append({
                    "type": "lazy",
                    "query": query,
                    "requester": ctx.author
                })
                added_count += 1
            
            if added_count > 1:
                await ctx.send(f"✅ 成功將 **{added_count}** 首歌從 Spotify 轉換至劇院！(延遲解析啟用)")

    @commands.command(name='play', aliases=['播放', '播', 'p'])
    async def play(self, ctx, *, search):
        if not ctx.voice_client:
            if not ctx.author.voice: return await ctx.send("❌ 你必須先加入語音頻道！")
            await ctx.author.voice.channel.connect(timeout=60.0, reconnect=True)

        if "open.spotify.com" in search:
            return await self.resolve_spotify(ctx, search)
            
        is_url = search.startswith("http")
        
        async with ctx.typing():
            try:
                state = self.get_state(ctx.guild.id)
                if not is_url:
                    data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{search}", download=False))
                    if not data or 'entries' not in data:
                        return await ctx.send("❌ 找不到相關結果。")
                    
                    results = data['entries']
                    view = MusicSelectView(self, results, ctx.author)
                    return await ctx.send(f"🔍 **為您找到與 `{search}` 相關的結果：**", view=view)

                kuji = self.bot.get_cog("KujiCog")
                is_prem = kuji and kuji.is_premium(ctx.author.id)
                player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True, 
                                                 volume=state['volume'], pitch=state['pitch'], 
                                                 theater=is_prem and state.get('theater', True), 
                                                 exciter=is_prem and state.get('exciter', True), 
                                                 bass=is_prem and state.get('bass', True), 
                                                 requester=ctx.author)
                
                if ctx.voice_client.is_playing():
                    gid = ctx.guild.id
                    if gid not in self.queue: self.queue[gid] = []
                    self.queue[gid].append(player)
                    await ctx.send(f"✅ **{player.title}** 已加入播放清單！")
                else:
                    self._play_song(ctx, player)
            except Exception as e: await ctx.send(f"❌ 播放錯誤: {e}")

    @commands.command(name='queue', aliases=['清單', '列表', 'q'])
    async def queue_cmd(self, ctx):
        gid = ctx.guild.id
        vc = ctx.voice_client
        
        if not vc or not vc.is_playing():
            return await ctx.send("❌ 劇院沒有在播歌喔！")
            
        embed = discord.Embed(title="📜 Yokaro 劇院播放清單", color=0x3498db)
        source = vc.source
        embed.add_field(name="▶️ 正在播放", value=f"**{source.title}**\n(點歌者: {source.requester.mention})", inline=False)
        
        q = self.queue.get(gid, [])
        if q:
            q_str = ""
            total_duration = 0
            for i, s in enumerate(q[:15]): 
                if isinstance(s, dict) and s.get('type') == 'lazy':
                    title = s['query'].replace('ytsearch1:', '').replace('audio', '').strip()
                    q_str += f"`{i+1}.` {title[:30]} | 延遲解析 (點歌者: {s['requester'].display_name})\n"
                else:
                    q_str += f"`{i+1}.` {s.title[:30]} | {str(timedelta(seconds=s.duration))} (點歌者: {s.requester.display_name})\n"
                    total_duration += s.duration
            
            if len(q) > 15: q_str += f"\n*...以及其他 {len(q)-15} 首歌*"
            embed.add_field(name=f"📜 待播清單 ({len(q)} 首)", value=q_str, inline=False)
            embed.set_footer(text=f"總時長: {str(timedelta(seconds=total_duration))}")
        else:
            embed.add_field(name="📜 待播清單", value="清單是空的！快來點歌！", inline=False)
            
        await ctx.send(embed=embed)

    def _play_song(self, ctx, player):
        state = self.get_state(ctx.guild.id)
        state['current_url'] = player.original_url or player.url
        state['elapsed'] = 0
        state['last_elapsed'] = 0
        player.start_time = time.time()
        
        if player.requester:
            uid = str(player.requester.id)
            if uid not in getattr(self, 'history', {}): self.history[uid] = []
            self.history[uid].append(player.title)
            self._save_history()

        try:
            if hasattr(ctx.voice_client.channel, 'edit'):
                asyncio.run_coroutine_threadsafe(
                    ctx.voice_client.channel.edit(status=f"🎶 正在播放：{player.title[:30]}"), 
                    self.bot.loop
                )
        except:
            pass

        def after_playing(error):
            if error: print(f"播放錯誤: {error}")
            try:
                if hasattr(ctx.voice_client.channel, 'edit'):
                    asyncio.run_coroutine_threadsafe(
                        ctx.voice_client.channel.edit(status=""), 
                        self.bot.loop
                    )
            except: pass
            self.play_next(ctx)

        ctx.voice_client.play(player, after=after_playing)
        asyncio.run_coroutine_threadsafe(self.send_panel(ctx, player), self.bot.loop)

    async def send_panel(self, ctx, player):
        embed = self.create_music_embed(ctx.guild.id, player, 0)
        view = MusicControlView(self)
        msg = await ctx.send(embed=embed, view=view)
        self.panels[ctx.guild.id] = msg

    def play_next(self, ctx):
        gid = ctx.guild.id
        if gid in self.queue and self.queue[gid] and ctx.voice_client:
            player = self.queue[gid].pop(0)
            
            if isinstance(player, dict) and player.get('type') == 'lazy':
                async def _resolve_and_play():
                    try:
                        state = self.get_state(gid)
                        kuji = self.bot.get_cog("KujiCog")
                        is_prem = kuji and kuji.is_premium(player['requester'].id)
                        real_player = await YTDLSource.from_url(player['query'], loop=self.bot.loop, stream=True, 
                                                                volume=state['volume'], pitch=state['pitch'], 
                                                                theater=is_prem and state.get('theater', True), 
                                                                exciter=is_prem and state.get('exciter', True), 
                                                                bass=is_prem and state.get('bass', True), 
                                                                requester=player['requester'])
                        self._play_song(ctx, real_player)
                    except Exception as e:
                        print(f"Lazy Load Error: {e}")
                        self.play_next(ctx)
                asyncio.run_coroutine_threadsafe(_resolve_and_play(), self.bot.loop)
                return

            self._play_song(ctx, player)
        else:
            if gid in self.panels:
                self.panels.pop(gid)

    @commands.command(name='skip', aliases=['跳過'])
    async def skip(self, ctx):
        if ctx.voice_client:
            ctx.voice_client.stop()
            await ctx.send("⏭️ 已跳過當前歌曲！")

    @commands.command(name='stop', aliases=['停止', '斷開', '下班'])
    async def stop(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.queue[ctx.guild.id] = []
            if ctx.guild.id in self.panels: self.panels.pop(ctx.guild.id)
            await ctx.send("🛑 劇院已關閉，洛洛下班啦～")

    @commands.command(name='shuffle', aliases=['亂序'])
    async def shuffle(self, ctx):
        if ctx.guild.id in self.queue and len(self.queue[ctx.guild.id]) > 0:
            random.shuffle(self.queue[ctx.guild.id])
            await ctx.send("🔀 **隊列已隨機亂序！**")
        else:
            await ctx.send("隊列是空的喔！")

    @commands.command(name='playnext', aliases=['pn', '插隊'])
    async def playnext(self, ctx, *, search):
        await ctx.send("⏭️ 此功能在 Pro 版開發中，敬請期待更穩定的插入演算法！")

    @commands.command(name='247')
    @commands.has_permissions(administrator=True)
    async def toggle_247(self, ctx):
        state = self.get_state(ctx.guild.id)
        state['247'] = not state.get('247', False)
        status = "✅ 已開啟 (洛洛將永不離開)" if state['247'] else "❌ 已關閉"
        await ctx.send(f"🌌 **24/7 模式 {status}**")

    @commands.command(name='8d')
    async def spatial(self, ctx):
        kuji = self.bot.get_cog("KujiCog")
        if kuji and not kuji.is_premium(ctx.author.id):
            return await ctx.send("💎 **8D 環繞為 Premium 專屬功能！** 請去抽個 A 賞吧！")
        
        state = self.get_state(ctx.guild.id)
        state['theater'] = True
        state['exciter'] = True
        state['bass'] = True
        await self.reload_current(ctx.guild)
        await ctx.send("🎧 **8D 虛擬環繞頂級音效已全開！**")

    @commands.command(name='recap', aliases=['回顧', '紀錄'])
    async def recap(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        uid = str(target.id)
        if uid not in getattr(self, 'history', {}) or not self.history[uid]:
            return await ctx.send(f"📊 **{target.display_name}** 還沒有留下聽歌紀錄喔！")
        
        songs = self.history[uid]
        counts = {}
        for s in songs: counts[s] = counts.get(s, 0) + 1
        top_songs = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        desc = f"🎧 **{target.display_name} 的音樂 DNA**\n\n"
        for i, (title, count) in enumerate(top_songs):
            desc += f"**{i+1}.** {title[:40]}... (點播 {count} 次)\n"
            
        embed = discord.Embed(title="📊 Yokaro 年度聽歌排行", description=desc, color=0x9b59b6)
        embed.set_footer(text=f"總點播次數: {len(songs)} 首", icon_url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='radio', aliases=['廣播電台'])
    async def radio(self, ctx, *, station):
        if not ctx.voice_client:
            if not ctx.author.voice: return await ctx.send("❌ 你必須先加入語音頻道！")
            await ctx.author.voice.channel.connect(timeout=60.0, reconnect=True)
            
        await ctx.send(f"📻 **正在為您調頻至 {station}...**")
        search = f"ytsearch1: 台灣 {station} 廣播 live"
        
        try:
            state = self.get_state(ctx.guild.id)
            kuji = self.bot.get_cog("KujiCog")
            is_prem = kuji and kuji.is_premium(ctx.author.id)
            player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True, 
                                             volume=state['volume'], pitch=1.0, 
                                             theater=is_prem, exciter=is_prem, bass=is_prem, requester=ctx.author)
            
            if ctx.voice_client.is_playing():
                gid = ctx.guild.id
                if gid not in self.queue: self.queue[gid] = []
                self.queue[gid].append(player)
                await ctx.send(f"✅ **{player.title}** 已加入清單！")
            else:
                self._play_song(ctx, player)
        except Exception as e:
            await ctx.send("❌ 無法連接該電台或找不到訊號源。")

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
