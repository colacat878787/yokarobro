import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import random
import yt_dlp
from utils.config import config_manager

# --- YTDL Search Helper ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': 'True',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch'
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class MusicRecommendCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hourly_check.start()

    def cog_unload(self):
        self.hourly_check.cancel()

    @tasks.loop(minutes=1)
    async def hourly_check(self):
        """每分鐘檢查一次是否為台北時間整點"""
        # 台北時間 UTC+8
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        if now.minute == 0:
            print(f"⏰ [整點推送] 台北時間 {now.hour}:00，準備發送推薦歌曲...")
            await self.push_recommendations()
            # 為了避免同一分鐘重複觸發，推完後稍微等一下
            await asyncio.sleep(61)

    async def push_recommendations(self):
        for guild in self.bot.guilds:
            settings = config_manager.get_guild_settings(guild.id)
            if not settings.get("recommend_enabled", True):
                continue
            
            channel_id = settings.get("recommend_channel")
            if not channel_id:
                # 用戶要求：沒設定就不發
                continue
            
            channel = guild.get_channel(int(channel_id))
            if channel:
                artist = random.choice(settings.get("recommend_artists", ["Jay Chou"]))
                await self.send_recommendation(channel, artist, is_auto=True)

    async def send_recommendation(self, channel, artist, is_auto=False):
        async with channel.typing():
            try:
                # 搜尋隨機一首歌
                search_query = f"{artist} official music video"
                data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))
                
                if 'entries' in data and data['entries']:
                    video = random.choice(data['entries'][:5]) # 從前5個隨機挑
                    title = video.get('title')
                    url = video.get('webpage_url')
                    duration = video.get('duration')
                    
                    embed = discord.Embed(
                        title=f"🎵 {'整點' if is_auto else '洛洛'}隨機推歌！",
                        description=f"今日推薦歌手：**{artist}**\n正在為您點播：**{title}**",
                        color=0xe91e63,
                        url=url
                    )
                    embed.set_thumbnail(url=video.get('thumbnail'))
                    embed.add_field(name="⏱️ 長度", value=f"{duration // 60}:{duration % 60:02d}", inline=True)
                    embed.set_footer(text="洛洛音樂電台 | 每一小時 的浪漫 嗷嗷嗷～")
                    
                    await channel.send(content=f"🌌 叮咚！{'整點到了，' if is_auto else ''}來聽首 **{artist}** 的歌吧！\n{url}", embed=embed)
                else:
                    if not is_auto: await channel.send(f"❌ 嗷～找不到 **{artist}** 的歌，可能他最近沒發片？")
            except Exception as e:
                print(f"推薦出錯: {e}")
                if not is_auto: await channel.send(f"❌ 推薦歌曲時發生錯誤：{e}")

    @commands.command(name='m推', aliases=['music_recommend', '推歌'])
    async def m_recommend(self, ctx):
        """手動觸發一張隨機推薦卡片"""
        settings = config_manager.get_guild_settings(ctx.guild.id)
        artists = settings.get("recommend_artists", ["周杰倫"])
        artist = random.choice(artists)
        await self.send_recommendation(ctx.channel, artist, is_auto=False)

async def setup(bot):
    await bot.add_cog(MusicRecommendCog(bot))
