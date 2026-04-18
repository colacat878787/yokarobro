import discord
from discord.ext import commands, tasks
from discord import app_commands
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

    @tasks.loop(minutes=10)
    async def hourly_check(self):
        """每 10 分鐘檢查一次並推送"""
        print(f"⏰ [定期推送] 準備發送 10 分鐘一回的推薦歌曲...")
        await self.push_recommendations()

    async def push_recommendations(self):
        for guild in self.bot.guilds:
            settings = config_manager.get_guild_settings(guild.id)
            if not settings.get("recommend_enabled", True):
                continue
            
            channel_id = settings.get("recommend_channel")
            if not channel_id:
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
                        title=f"🎵 {'定時' if is_auto else '洛洛'}隨機推歌！",
                        description=f"今日推薦歌手：**{artist}**\n正在為您點播：**{title}**",
                        color=0xe91e63,
                        url=url
                    )
                    embed.set_thumbnail(url=video.get('thumbnail'))
                    embed.add_field(name="⏱️ 長度", value=f"{duration // 60}:{duration % 60:02d}", inline=True)
                    embed.set_footer(text="洛洛音樂電台 | 每 10 分鐘一次的驚喜 嗷嗷嗷～")
                    
                    await channel.send(content=f"🌌 叮咚！{'來份音樂點心吧，' if is_auto else ''}推薦歌手：**{artist}**！\n{url}", embed=embed)
                else:
                    if not is_auto: await channel.send(f"❌ 嗷～找不到 **{artist}** 的歌...")
            except Exception as e:
                print(f"推薦出錯: {e}")
                if not is_auto: await channel.send(f"❌ 推薦歌曲時發生錯誤：{e}")

    @commands.hybrid_command(name='m推', aliases=['music_recommend', '推歌'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def m_recommend(self, ctx, action: str = None):
        """手動推歌或設定頻道：!m推 或 !m推 set"""
        if action == "set":
            if not ctx.author.guild_permissions.administrator:
                return await ctx.send("❌ 只有管理員可以設定推薦頻道喔！")
            config_manager.set_guild_setting(ctx.guild.id, "recommend_channel", str(ctx.channel.id))
            await ctx.send(f"✅ 已成功將 {ctx.channel.mention} 設定為【每 10 分鐘推歌頻道】！")
        else:
            settings = config_manager.get_guild_settings(ctx.guild.id)
            artists = settings.get("recommend_artists", ["周杰倫"])
            artist = random.choice(artists)
            await self.send_recommendation(ctx.channel, artist, is_auto=False)

async def setup(bot):
    await bot.add_cog(MusicRecommendCog(bot))
