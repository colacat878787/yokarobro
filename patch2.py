import os
import re

with open('old_music_utf8.py', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

# 1. Update get_state for default filters
code = code.replace(
    "self.states[guild_id] = {'volume': 0.5, 'pitch': 1.0, 'theater': False, 'current_url': None, 'elapsed': 0}",
    "self.states[guild_id] = {'volume': 0.5, 'pitch': 1.0, 'theater': True, 'exciter': True, 'bass': True, 'current_url': None, 'elapsed': 0, '247': False}"
)

# 2. Update YTDLSource.from_url to accept new filters
code = re.sub(
    r'async def from_url\(cls, url, \*, loop=None, stream=False, volume=0\.5, pitch=1\.0, theater=False, seek=0, requester=None\):',
    'async def from_url(cls, url, *, loop=None, stream=False, volume=0.5, pitch=1.0, theater=True, exciter=True, bass=True, seek=0, requester=None):',
    code
)

# 3. Update YTDLSource.__init__
code = re.sub(
    r'def __init__\(self, source, \*, data, volume=0\.5, pitch=1\.0, theater=False, requester=None\):',
    'def __init__(self, source, *, data, volume=0.5, pitch=1.0, theater=True, exciter=True, bass=True, requester=None):',
    code
)
code = code.replace('self.theater = theater', 'self.theater = theater\n        self.exciter = exciter\n        self.bass = bass')

# 4. Update FFmpeg filters
filter_code = """        filters = []
        if theater: filters.append("extrastereo=m=2.5")
        if exciter: filters.append("highpass=f=200, treble=g=5")
        if bass: filters.append("bass=g=10:f=110:w=0.6")
        if pitch != 1.0: filters.append(f"asetrate=48000*{pitch},atempo=1/{pitch}")
        if not filters: filters.append("loudnorm")"""
code = re.sub(r'        filters = \[\]\n        if theater: filters\.append\("extrastereo=m=2\.5"\)\n        if pitch != 1\.0: filters\.append\(f"asetrate=48000\*{pitch},atempo=1/{pitch}"\)', filter_code, code)

# 5. Update reload_current call
code = code.replace(
    "theater=state['theater'], seek=int(current_elapsed), requester=vc.source.requester",
    "theater=state['theater'], exciter=state.get('exciter', True), bass=state.get('bass', True), seek=int(current_elapsed), requester=vc.source.requester"
)

# 6. Update play and resolve_spotify to pass filters
code = code.replace("theater=state['theater'], requester=ctx.author)", "theater=state['theater'], exciter=state.get('exciter', True), bass=state.get('bass', True), requester=ctx.author)")

# 7. Add history tracking and new commands
init_addition = """        self.history_file = "music_history.json"
        self.history = self._load_history()

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                import json
                with open(self.history_file, 'r', encoding='utf-8') as f: return json.load(f)
            except: pass
        return {}

    def _save_history(self):
        import json
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f)"""
code = code.replace('self.update_panel_task.start()', 'self.update_panel_task.start()\n' + init_addition)

play_song_replace = """        state['current_url'] = player.original_url or player.url
        state['elapsed'] = 0
        state['last_elapsed'] = 0
        player.start_time = time.time()
        
        if player.requester:
            uid = str(player.requester.id)
            if getattr(self, 'history', None) is not None:
                if uid not in self.history: self.history[uid] = []
                self.history[uid].append(player.title)
                self._save_history()"""
code = code.replace("""        state['current_url'] = player.original_url or player.url
        state['elapsed'] = 0
        state['last_elapsed'] = 0
        player.start_time = time.time()""", play_song_replace)

new_commands = """
    @commands.command(name='shuffle', aliases=['亂序'])
    async def shuffle(self, ctx):
        if ctx.guild.id in self.queue and len(self.queue[ctx.guild.id]) > 0:
            import random
            random.shuffle(self.queue[ctx.guild.id])
            await ctx.send("🔀 **隊列已隨機亂序！**")
        else:
            await ctx.send("隊列是空的喔！")

    @commands.command(name='playnext', aliases=['pn', '插隊'])
    async def playnext(self, ctx, *, search):
        await ctx.send("⏭️ 插隊功能開發中，敬請期待！")

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
"""
code += new_commands

with open('cogs/music.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Patch applied")
