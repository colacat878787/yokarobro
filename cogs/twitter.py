import discord
from discord.ext import commands, tasks
import feedparser
import aiohttp
import os
import asyncio

# 公開 Nitter 實例列表 (若掛掉請自行更換)
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.cz",
    "https://nitter.it",
    "https://nitter.privacydev.net"
]

class TwitterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_posts = {} # screen_name: last_link
        self.monitored_users = ["elonmusk", "index96703"] # 預設追蹤
        self.target_channel_id = None # 設定要發送通知的頻道
        self.check_twitter.start()

    def cog_unload(self):
        self.check_twitter.cancel()

    @commands.command(name='track_x', aliases=['追蹤推特'])
    async def track_x(self, ctx, username: str):
        """新增追蹤 Twitter(X) 使用者"""
        if username not in self.monitored_users:
            self.monitored_users.append(username)
            self.target_channel_id = ctx.channel.id
            await ctx.send(f"嗷～開始追蹤 **{username}** 的推特！會在這裡發送通知喔。")
        else:
            await ctx.send(f"嗷～**{username}** 已經在名單裡了。")

    @tasks.loop(minutes=10) # 10 分鐘檢查一次，避免被封 IP
    async def check_twitter(self):
        if not self.target_channel_id: return
        channel = self.bot.get_channel(self.target_channel_id)
        if not channel: return

        for username in self.monitored_users:
            # 優先使用第一個 instance
            rss_url = f"{NITTER_INSTANCES[0]}/{username}/rss"
            try:
                # 使用 aiohttp 獲取 content 後交給 feedparser
                async with aiohttp.ClientSession() as session:
                    async with session.get(rss_url, timeout=10) as response:
                        if response.status == 200:
                            content = await response.text()
                            feed = feedparser.parse(content)
                            if feed.entries:
                                latest = feed.entries[0]
                                link = latest.link
                                
                                # 檢查是否為新貼文
                                if username not in self.last_posts or self.last_posts[username] != link:
                                    self.last_posts[username] = link
                                    
                                    # 轉換為真實 Twitter 連結
                                    real_link = link.replace(NITTER_INSTANCES[0], "https://twitter.com")
                                    
                                    embed = discord.Embed(
                                        title=f"🔔 {username} 發布了新推文！",
                                        description=latest.description[:200] + "...",
                                        url=real_link,
                                        color=0x1da1f2
                                    )
                                    embed.set_footer(text="洛洛推特情報站 (via Nitter RSS)")
                                    await channel.send(embed=embed)
                        else:
                            print(f"Twitter check failed for {username}: Status {response.status}")
            except Exception as e:
                print(f"Twitter check error for {username}: {e}")
            
            await asyncio.sleep(2) # 每個用戶間隔 2 秒，防被禁

    @check_twitter.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(TwitterCog(bot))
