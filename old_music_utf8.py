import discord
from discord.ext import commands, tasks
import yt_dlp
import asyncio
import os
import time
import json
import re
from datetime import timedelta

# --- YTDL ?蔭 ---
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

        # ?? yt-dlp 撱箄降??HTTP Headers (閫?捱 B蝡?403 ??)
        headers = data.get('http_headers', {})
        header_str = "".join([f"{k}: {v}\r\n" for k, v in headers.items()])

        filters = []
        if theater: filters.append("extrastereo=m=2.5")
        if pitch != 1.0: filters.append(f"asetrate=48000*{pitch},atempo=1/{pitch}")
        
        af_string = f"-af \"{','.join(filters)}\"" if filters else ""
        ffmpeg_options = {
            'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {seek}',
            'options': f'-vn {af_string}'
        }
        
        # 憒???headers嚗??亙 FFmpeg
        if header_str:
            ffmpeg_options['before_options'] += f' -headers "{header_str}"'

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, volume=volume, pitch=pitch, theater=theater, requester=requester)

# ?? ???璅?園????
class MusicControlView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="?殷?", style=discord.ButtonStyle.secondary, custom_id="mus_prev", row=0)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("? 瘣?????甇??銝哨??急??芾頝喲???", ephemeral=True)

    @discord.ui.button(label="?賂?/?塚?", style=discord.ButtonStyle.primary, custom_id="mus_pause", row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return await interaction.response.send_message("??瘝?甇??剖?璅?, ephemeral=True)
        if vc.is_paused(): vc.resume()
        else: vc.pause()
        await interaction.response.defer()

    @discord.ui.button(label="?哨? 頝喲?", style=discord.ButtonStyle.primary, custom_id="mus_skip", row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
        await interaction.response.defer()

    @discord.ui.button(label="?對? ?迫", style=discord.ButtonStyle.danger, custom_id="mus_stop", row=0)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            self.cog.queue[interaction.guild_id] = []
        await interaction.response.defer()

    @discord.ui.button(label="??", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_vol_down")
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_vol(interaction, -0.1)

    @discord.ui.button(label="??", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_vol_up")
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_vol(interaction, 0.1)

    @discord.ui.button(label="?-", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_pitch_down")
    async def pitch_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_pitch(interaction, -0.05)

    @discord.ui.button(label="?+", style=discord.ButtonStyle.secondary, row=1, custom_id="mus_pitch_up")
    async def pitch_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._adjust_pitch(interaction, 0.05)

    @discord.ui.button(label="?? ?蔭", style=discord.ButtonStyle.secondary, custom_id="mus_reset", row=1)
    async def reset_pitch(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(interaction.guild_id)
        state['pitch'] = 1.0
        await self.cog.reload_current(interaction.guild)
        await interaction.response.defer()

    @discord.ui.button(label="? ???璅∪?", style=discord.ButtonStyle.success, custom_id="mus_theater", row=2)
    async def dolby(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(interaction.guild_id)
        state['theater'] = not state['theater']
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
            await interaction.response.send_message("??暺??桐葉嚗瘜?雿?, ephemeral=True)
            return False
        if not interaction.user.voice or not interaction.guild.voice_client or \
           interaction.user.voice.channel.id != interaction.guild.voice_client.channel.id:
            await interaction.response.send_message("???選?憒喳??????典?銝???單鋆∴?", ephemeral=True)
            return False
        return True

# ?? ??蝯??詨 ??
class MusicSelectView(discord.ui.View):
    def __init__(self, cog, results, requester):
        super().__init__(timeout=60)
        self.cog = cog
        self.results = results
        self.requester = requester
        
        # 撱箇??詨
        select = discord.ui.Select(placeholder="? ?訾?擐??唾???改?", min_values=1, max_values=1)
        for i, res in enumerate(results):
            title = res.get('title', '?芰璅?')[:100]
            duration = str(timedelta(seconds=res.get('duration', 0)))
            select.add_option(
                label=title,
                value=str(i),
                description=f"?: {duration} | ?駁?: {res.get('uploader', '?芰')[:50]}",
                emoji="?"
            )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            return await interaction.response.send_message("?????臭???撠???嚗?, ephemeral=True)
            
        await interaction.response.defer()
        idx = int(interaction.data['values'][0])
        res = self.results[idx]
        url = res.get('webpage_url') or res.get('url')
        
        # 璅⊥暺?銵
        ctx = await self.cog.bot.get_context(interaction.message)
        ctx.author = self.requester # 靽格迤暺???        await self.cog.play(ctx, search=url)
        
        # 蝘駁?詨閮
        await interaction.delete_original_response()

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

    # --- ?脣漲璇??Ｘ?湔 ---
    def create_progress_bar(self, current, total):
        if total == 0: return "[???砂?砂?砂?砂?砂]"
        percent = current / total
        bar_len = 10
        filled = int(percent * bar_len)
        bar = list("?砂?砂?砂?砂?砂")
        if 0 <= filled < bar_len: bar[filled] = "??"
        elif filled >= bar_len: bar[-1] = "??"
        else: bar[0] = "??"
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
                
                # 閮???
                elapsed = int(time.time() - source.start_time + state.get('elapsed', 0))
                if vc.is_paused(): elapsed = int(state.get('last_elapsed', elapsed))
                state['last_elapsed'] = elapsed

                # 瑽遣 Embed
                embed = self.create_music_embed(guild_id, source, elapsed)
                await message.edit(embed=embed, view=MusicControlView(self))
            except Exception as e:
                # ????嚗?隤???                pass

    def create_music_embed(self, guild_id, source, elapsed):
        state = self.get_state(guild_id)
        total = source.duration
        
        embed = discord.Embed(title=f"? 甇??剜嚗source.title}", color=0xed4245)
        if hasattr(source, 'thumbnail') and source.thumbnail: 
            embed.set_image(url=source.thumbnail)
        
        # ?脣漲璇?        bar = self.create_progress_bar(elapsed, total)
        time_str = f"`{str(timedelta(seconds=elapsed)).split('.')[0]} / {str(timedelta(seconds=total)).split('.')[0]}`"
        
        embed.description = f"{bar} {time_str}\n\n? **暺???*嚗source.requester.mention if source.requester else '?芰'}"
        
        # 敺皜 (蝎曄陛??
        q = self.queue.get(guild_id, [])
        if q:
            q_list = "\n".join([f"**{i+1}.** {s.title}" for i, s in enumerate(q[:3])])
            if len(q) > 3: q_list += f"\n*...隞亙??嗡? {len(q)-3} 擐???(頛詨 !queue ?亦??券)*"
            embed.add_field(name="?? 敺皜", value=q_list, inline=False)
        else:
            embed.add_field(name="?? 敺皜", value="?桀?瘝?銝?擐??莎?敹思?暺??改?", inline=False)

        # ???        status = f"?? {int(state['volume']*100)}% | ? {state['pitch']:.2f}x | ? {'??? ON' if state['theater'] else 'OFF'}"
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

    # --- Spotify 頝典像?啗圾? (?游?閫?? B 璅∪?) ---
    async def resolve_spotify(self, ctx, url):
        async with ctx.typing():
            tracks = [] # ?脣?敺?撠?甇?皜
            
            # --- 蝑 A: 雿輻 python -m yt_dlp ?? JSON ---
            try:
                import sys
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, '-m', 'yt_dlp', '--dump-json', '--flat-playlist', url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
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
                if tracks: print(f"??蝑 A (yt-dlp) ???? {len(tracks)} 擐???)
            except: pass

            # --- 蝑 B: 雿輻 Spotify oEmbed API (??A 憭望???脫?) ---
            if not tracks:
                try:
                    async with aiohttp.ClientSession() as session:
                        oembed_url = f"https://open.spotify.com/oembed?url={url}"
                        async with session.get(oembed_url) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                title = data.get('title')
                                artist = data.get('provider_name', '') # oEmbed ???暸?                                if title:
                                    tracks = [f"{title} {artist}"]
                                    print("??蝑 B (oEmbed) ?????格鞈?")
                except: pass

            # --- 蝑 C: ?游?蝬脤? Meta ?祈 (?敺蝺? ---
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
                                    artist = raw_desc.split('繚')[0].strip() if '繚' in raw_desc else raw_desc
                                    tracks = [f"{raw_title} {artist}"]
                                    print("??蝑 C (Scraper) ???? Meta")
                except: pass

            if not tracks:
                return await ctx.send("??瘣??∪?鈭???????脰風憭芸撥嚗圾??鈭?嚗?)

            # --- 蝯曹?????暸?頛?---
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
                except Exception as e:
                    print(f"Search error for '{query}': {e}")
                    continue
            
            if added_count > 1:
                await ctx.send(f"??撌脣???圾????撠?**{added_count}** 擐??脣? Spotify ?砍 YouTube ?剜嚗??)
            elif added_count == 0:
                await ctx.send("????...?閫???唳???雿 YouTube 銝銝?賢???研?)

    @commands.command(name='play', aliases=['?剜', '??])
    async def play(self, ctx, *, search):
        if not ctx.voice_client:
            if not ctx.author.voice: return await ctx.send("?瘀?雿??刻??喲?塚?")
            await ctx.author.voice.channel.connect(timeout=60.0, reconnect=True)

        if "open.spotify.com" in search:
            return await self.resolve_spotify(ctx, search)
            
        # ?斗?臬?箇雯?
        is_url = search.startswith("http")
        
        async with ctx.typing():
            try:
                state = self.get_state(ctx.guild.id)
                
                # 憒??舫??萄???嚗??粹??                if not is_url:
                    # ?? 5 ??撠???                    data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{search}", download=False))
                    if not data or 'entries' not in data:
                        return await ctx.send("???曆??啁????蝯???)
                    
                    results = data['entries']
                    view = MusicSelectView(self, results, ctx.author)
                    return await ctx.send(f"?? **憭抒蜇鋆????search}????蝯?嚗?*", view=view)

                # 憒??舐雯?嚗?交??                player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True, 
                                                 volume=state['volume'], pitch=state['pitch'], 
                                                 theater=state['theater'], requester=ctx.author)
                
                if ctx.voice_client.is_playing():
                    gid = ctx.guild.id
                    if gid not in self.queue: self.queue[gid] = []
                    self.queue[gid].append(player)
                    await ctx.send(f"??**{player.title}** 撌脣??交?暹???)
                else:
                    self._play_song(ctx, player)
            except Exception as e: await ctx.send(f"???剜憭望?: {e}")

    @commands.command(name='queue', aliases=['皜', '?”', 'q'])
    async def queue_cmd(self, ctx):
        """?亦??桀???暹???""
        gid = ctx.guild.id
        vc = ctx.voice_client
        
        if not vc or not vc.is_playing():
            return await ctx.send("???桀?瘝?甇??剜?璅?)
            
        embed = discord.Embed(title="?? ?單???剜?”", color=0x3498db)
        
        # 甇??剜
        source = vc.source
        embed.add_field(name="?塚? 甇??剜", value=f"**{source.title}**\n(暺??? {source.requester.mention})", inline=False)
        
        # 敺皜
        q = self.queue.get(gid, [])
        if q:
            q_str = ""
            total_duration = 0
            for i, s in enumerate(q[:15]): # ?憭＊蝷?15 擐?                q_str += f"`{i+1}.` {s.title} | {str(timedelta(seconds=s.duration))} (? {s.requester.display_name})\n"
                total_duration += s.duration
            
            if len(q) > 15:
                q_str += f"\n*...隞亙??嗡? {len(q)-15} 擐???"
            
            embed.add_field(name=f"??敺銝?({len(q)} 擐?", value=q_str, inline=False)
            embed.set_footer(text=f"蝮賢??剜??? {str(timedelta(seconds=total_duration))}")
        else:
            embed.add_field(name="??敺銝?, value="皜?舐征??敹怠暺??改?", inline=False)
            
        await ctx.send(embed=embed)


    def _play_song(self, ctx, player):
        state = self.get_state(ctx.guild.id)
        state['current_url'] = player.original_url or player.url
        state['elapsed'] = 0
        state['last_elapsed'] = 0
        player.start_time = time.time()
        
        # 摰儔?剜蝯?敺??? (??航炊??)
        def after_playing(error):
            if error:
                print(f"?剜???粹: {error}")
                asyncio.run_coroutine_threadsafe(
                    ctx.send(f"?? **?剜?粹?佗?**\n瘣????岫?望????暺?憭?`{error}`\n?虜?舫閮?皞?(憒?B蝡? ?????撠??嚗??), 
                    self.bot.loop
                )
            self.play_next(ctx)

        ctx.voice_client.play(player, after=after_playing)
        
        # ?潮??        asyncio.run_coroutine_threadsafe(self.send_panel(ctx, player), self.bot.loop)

    async def send_panel(self, ctx, player):
        embed = self.create_music_embed(ctx.guild.id, player, 0)
        view = MusicControlView(self)
        msg = await ctx.send(embed=embed, view=view)
        self.panels[ctx.guild.id] = msg

    def play_next(self, ctx):
        gid = ctx.guild.id
        if gid in self.queue and self.queue[gid] and ctx.voice_client:
            player = self.queue[gid].pop(0)
            self._play_song(ctx, player)
        else:
            if gid in self.panels:
                # ?剜蝯?嚗??日??                self.panels.pop(gid)

    @commands.command(name='skip', aliases=['頝喲?'])
    async def skip(self, ctx):
        if ctx.voice_client:
            ctx.voice_client.stop()
            await ctx.send("??撌脰歲????莎?")

    @commands.command(name='stop', aliases=['?迫', '?琿?', '銝'])
    async def stop(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.queue[ctx.guild.id] = []
            if ctx.guild.id in self.panels: self.panels.pop(ctx.guild.id)
            await ctx.send("?? 撌脣?甇Ｘ?曆蒂皜征皜??)

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
