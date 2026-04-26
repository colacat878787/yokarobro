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

# ── 專業音效參數 ──
FILTER_PRESETS = {
    'bass': 'bass=g=15,loudnorm',
    'nightcore': 'asetrate=48000*1.25,atempo=1.25,highpass=f=200,loudnorm',
    'vaporwave': 'asetrate=48000*0.8,atempo=0.8,lowpass=f=3000,loudnorm',
    'exciter': 'firequalizer=gain_entry=\'entry(0,0);entry(200,0);entry(4000,5);entry(20000,10)\',loudnorm',
    'theater': 'extrastereo=m=2.5,loudnorm'
}

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True, 'noplaylist': True, 'nocheckcertificate': True,
    'ignoreerrors': False, 'logtostderr': False, 'quiet': True, 'no_warnings': True,
    'default_search': 'auto', 'source_address': '0.0.0.0',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

def is_rickroll(title):
    if not title: return False
    kws = ["never gonna give you up", "rickroll", "rick roll", "nevergonnagiveyouup"]
    t = title.lower().replace(" ", "")
    return any(kw.replace(" ", "") in t for kw in kws)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, pitch=1.0, requester=None):
        super().__init__(source, volume)
        self.data = data
        self.title, self.url = data.get('title'), data.get('url')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')
        self.requester = requester
        self.start_time = time.time()
        self.original_url = data.get('webpage_url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, volume=0.5, pitch=1.0, filters=None, seek=0, requester=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data: data = data['entries'][0]
        
        af = []
        if filters:
            for f in filters:
                if f in FILTER_PRESETS: af.append(FILTER_PRESETS[f])
        if pitch != 1.0: af.append(f"asetrate=48000*{pitch},atempo=1/{pitch}")
        if not af: af.append("loudnorm=I=-16:TP=-1.5:LRA=11") # 預設 AGC

        opts = {
            'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {seek}',
            'options': f'-vn -af "{",".join(af)}"'
        }
        return cls(discord.FFmpegPCMAudio(data['url'], **opts), data=data, volume=volume, pitch=pitch, requester=requester)

class MusicControlView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def update_btns(self, interaction):
        state = self.cog.get_state(interaction.guild_id)
        # 這裡可以根據 state 改變按鈕樣式
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏸️", style=discord.ButtonStyle.primary, row=0)
    async def pause_resume(self, interaction, button):
        vc = interaction.guild.voice_client
        if vc.is_paused(): vc.resume(); button.label = "⏸️"
        else: vc.pause(); button.label = "▶️"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.primary, row=0)
    async def skip(self, interaction, button):
        if interaction.guild.voice_client: interaction.guild.voice_client.stop()
        await interaction.response.defer()

    @discord.ui.button(label="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def loop(self, interaction, button):
        state = self.cog.get_state(interaction.guild_id)
        modes = [None, 'single', 'queue']
        state['loop'] = modes[(modes.index(state.get('loop')) + 1) % 3]
        button.label = {None: "🔁", 'single': "🔂", 'queue': "🔁 [Q]"}[state['loop']]
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="📻 續播: ON", style=discord.ButtonStyle.success, row=0)
    async def toggle_autoplay(self, interaction, button):
        state = self.cog.get_state(interaction.guild_id)
        state['autoplay'] = not state.get('autoplay', True)
        button.label = f"📻 續播: {'ON' if state['autoplay'] else 'OFF'}"
        button.style = discord.ButtonStyle.success if state['autoplay'] else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="🔊+", style=discord.ButtonStyle.secondary, row=1)
    async def vol_up(self, interaction, button):
        state = self.cog.get_state(interaction.guild_id)
        state['volume'] = min(1.0, state['volume'] + 0.1)
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = state['volume']
        await interaction.response.defer()

    @discord.ui.button(label="🔊-", style=discord.ButtonStyle.secondary, row=1)
    async def vol_down(self, interaction, button):
        state = self.cog.get_state(interaction.guild_id)
        state['volume'] = max(0.0, state['volume'] - 0.1)
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = state['volume']
        await interaction.response.defer()

    @discord.ui.button(label="🔥 Bass", style=discord.ButtonStyle.secondary, row=2)
    async def bass(self, interaction, button):
        await self.toggle_filter(interaction, 'bass')

    @discord.ui.button(label="⚡ Nightcore", style=discord.ButtonStyle.secondary, row=2)
    async def nc(self, interaction, button):
        await self.toggle_filter(interaction, 'nightcore')

    @discord.ui.button(label="🌊 Vapor", style=discord.ButtonStyle.secondary, row=2)
    async def vp(self, interaction, button):
        await self.toggle_filter(interaction, 'vaporwave')

    @discord.ui.button(label="🎬 杜比: OFF", style=discord.ButtonStyle.secondary, custom_id="mus_dolby", row=3)
    async def dolby(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_filter(interaction, 'theater', button)

    @discord.ui.button(label="✨ 修復 (💎)", style=discord.ButtonStyle.secondary, row=3)
    async def exciter(self, interaction, button):
        await self.toggle_filter(interaction, 'exciter', button, premium=True)

    async def toggle_filter(self, interaction, f, button=None, premium=False):
        kuji = self.cog.bot.get_cog("KujiCog")
        if premium and kuji and not kuji.is_premium(interaction.user.id):
            return await interaction.response.send_message("💎 **此為 Premium 專屬功能！**\n洛洛偵測到您尚未擁有會員資格。快去 `!一番賞` 抽個 SP 賞來解鎖這項黑科技吧！🐾🎟️", ephemeral=True)

        state = self.cog.get_state(interaction.guild_id)
        if f in state['filters']:
            state['filters'].remove(f)
            if button:
                button.style = discord.ButtonStyle.secondary
                if f == 'theater': button.label = "🎬 杜比: OFF"
        else:
            state['filters'].append(f)
            if button:
                button.style = discord.ButtonStyle.success
                if f == 'theater': button.label = "🎬 杜比: ON"
        
        await self.cog.reload_current(interaction.guild)
        await interaction.response.edit_message(view=self)

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue, self.panels, self.states = {}, {}, {}
        self.precache = {} # gid: next_player
        self.update_task.start()

    def get_state(self, gid):
        if gid not in self.states: self.states[gid] = {'volume': 0.5, 'pitch': 1.0, 'filters': [], 'loop': None, 'autoplay': True, 'antirickroll': True, 'elapsed': 0}
        return self.states[gid]

    @tasks.loop(seconds=1)
    async def update_task(self):
        for gid, msg in list(self.panels.items()):
            try:
                guild = self.bot.get_guild(gid)
                if not guild or not guild.voice_client or not guild.voice_client.source: continue
                vc, source, state = guild.voice_client, guild.voice_client.source, self.get_state(gid)
                elapsed = int(time.time() - source.start_time + state.get('elapsed', 0))
                if vc.is_paused(): elapsed = int(state.get('last_elapsed', elapsed))
                state['last_elapsed'] = elapsed

                # 🚀 零延遲預緩衝：剩下 15 秒時開始準備
                if source.duration - elapsed <= 15 and gid not in self.precache:
                    asyncio.create_task(self.prepare_next(gid))

                # 🚀 自動修復：如果超過時長 3 秒還沒換歌，強制換歌
                if elapsed > source.duration + 3:
                    self.play_next(guild)
                    continue

                await msg.edit(embed=self.create_music_embed(gid, source, elapsed))
                if elapsed % 30 == 0: await vc.channel.edit(name=f"🎵 {source.title[:20]}...")
            except: pass

    async def prepare_next(self, gid):
        if gid in self.queue and self.queue[gid]:
            url = self.queue[gid][0] # 預測下一首
            if isinstance(url, str):
                state = self.get_state(gid)
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True, volume=state['volume'], filters=state['filters'], requester=self.bot.user)
                self.precache[gid] = player

    def create_music_embed(self, gid, source, elapsed):
        state = self.get_state(gid)
        vol_icon = "🔇" if state['volume'] == 0 else "🔉" if state['volume'] < 0.6 else "🔊"
        embed = discord.Embed(title=f"🎶 正在播放：{source.title}", color=0xed4245)
        embed.set_image(url=source.thumbnail)
        percent = min(elapsed / source.duration, 1.0) if source.duration > 0 else 0
        bar = list("▬▬▬▬▬▬▬▬▬▬")
        bar[min(int(percent * 10), 9)] = "🔘"
        filters_str = ", ".join(state['filters']) if state['filters'] else "無"
        is_dolby = "✅" if 'theater' in state['filters'] else "❌"
        embed.description = f"[{''.join(bar)}] `{timedelta(seconds=elapsed)} / {timedelta(seconds=source.duration)}`\n\n🎬 杜比: {is_dolby} | ✨ 濾鏡: `{filters_str.replace('theater', '杜比')}`\n📻 續播: `{'✅' if state['autoplay'] else '❌'}`"
        embed.set_footer(text=f"Yokaro Pro | {vol_icon} {int(state['volume']*100)}% | 點歌者: {source.requester.display_name if source.requester else '未知'}", icon_url=source.requester.display_avatar.url if source.requester else None)
        return embed

    @commands.command(name='playnext', aliases=['pn', '插隊'])
    async def playnext(self, ctx, *, search):
        if not ctx.voice_client: await ctx.author.voice.channel.connect()
        info = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
        if ctx.guild.id not in self.queue: self.queue[ctx.guild.id] = []
        self.queue[ctx.guild.id].insert(0, search)
        await ctx.send(f"⏭️ **{info.get('title')}** 已插隊至下一首！")

    @commands.command(name='shuffle', aliases=['亂序'])
    async def shuffle(self, ctx):
        if ctx.guild.id in self.queue:
            random.shuffle(self.queue[ctx.guild.id])
            await ctx.send("🔀 **隊列已隨機亂序！**")
        else:
            await ctx.send("隊列是空的喔！")

    @commands.command(name='247')
    @commands.has_permissions(administrator=True)
    async def toggle_247(self, ctx):
        state = self.get_state(ctx.guild.id)
        state['247'] = not state.get('247', False)
        status = "✅ 已開啟" if state['247'] else "❌ 已關閉"
        await ctx.send(f"🌌 **24/7 模式 {status}**")

    @commands.command(name='8d')
    async def spatial(self, ctx):
        kuji = self.bot.get_cog("KujiCog")
        if kuji and not kuji.is_premium(ctx.author.id):
            return await ctx.send("💎 **8D 環繞為 Premium 專屬功能！** 請去抽個 A 賞吧！")
        state = self.get_state(ctx.guild.id)
        if 'theater' in state['filters']: state['filters'].remove('theater')
        state['filters'].append('theater')
        await self.reload_current(ctx.guild)
        await ctx.send("🎧 **8D 虛擬環繞音效已啟動！**")

    @commands.command(name='play', aliases=['播放', '播', 'p'])
    async def play(self, ctx, *, search):
        if not ctx.voice_client: await ctx.author.voice.channel.connect()
        async with ctx.typing():
            state = self.get_state(ctx.guild.id)
            info = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
            if state['antirickroll'] and is_rickroll(info.get('title')): return await ctx.send("🚫 **偵測到 Rickroll，已攔截！**")
            
            if ctx.voice_client.is_playing():
                if ctx.guild.id not in self.queue: self.queue[ctx.guild.id] = []
                self.queue[ctx.guild.id].append(search)
                await ctx.send(f"✅ **{info.get('title')}** 已加入隊列！")
            else:
                player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True, volume=state['volume'], filters=state['filters'], requester=ctx.author)
                self._play_song(ctx, player)

    def _play_song(self, ctx, player):
        gid = ctx.guild.id
        state = self.get_state(gid)
        state['current_url'], state['elapsed'] = player.original_url, 0
        ctx.voice_client.play(player, after=lambda e: self.play_next(ctx.guild))
        asyncio.run_coroutine_threadsafe(self.send_panel(ctx, player), self.bot.loop)

    async def send_panel(self, ctx, player):
        view = MusicControlView(self)
        msg = await ctx.send(embed=self.create_music_embed(ctx.guild.id, player, 0), view=view)
        self.panels[ctx.guild.id] = msg

    def play_next(self, guild):
        gid = guild.id
        state = self.get_state(gid)
        if state['loop'] == 'single':
            asyncio.run_coroutine_threadsafe(self.reload_current(guild), self.bot.loop)
            return
        
        if gid in self.precache:
            player = self.precache.pop(gid)
            self.queue[gid].pop(0)
            self._play_song_raw(guild, player)
        elif gid in self.queue and self.queue[gid]:
            url = self.queue[gid].pop(0)
            asyncio.run_coroutine_threadsafe(self.play_url(guild, url), self.bot.loop)
        elif state['autoplay']:
            asyncio.run_coroutine_threadsafe(self.run_autoplay(guild), self.bot.loop)

    async def play_url(self, guild, url):
        state = self.get_state(guild.id)
        player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True, volume=state['volume'], filters=state['filters'], requester=self.bot.user)
        self._play_song_raw(guild, player)

    def _play_song_raw(self, guild, player):
        state = self.get_state(guild.id)
        state['current_url'], state['elapsed'] = player.original_url, 0
        guild.voice_client.play(player, after=lambda e: self.play_next(guild))
        # 更新面板 (此處略，通常會發新訊息或更新舊訊息)

    async def run_autoplay(self, guild):
        state = self.get_state(guild.id)
        data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(state['current_url'], download=False))
        if 'related_videos' in data:
            url = f"https://www.youtube.com/watch?v={data['related_videos'][0]['id']}"
            await self.play_url(guild, url)

    async def reload_current(self, guild):
        vc = guild.voice_client
        if not vc or not vc.source: return
        state = self.get_state(guild.id)
        elapsed = int(time.time() - vc.source.start_time + state.get('elapsed', 0))
        state['elapsed'] = elapsed
        player = await YTDLSource.from_url(state['current_url'], loop=self.bot.loop, stream=True, volume=state['volume'], filters=state['filters'], seek=elapsed, requester=vc.source.requester)
        vc.source = player
        player.start_time = time.time()

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
