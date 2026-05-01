import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import os
import json
from datetime import datetime

class OtakuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monitored_x = [
            "EN_BlueArchive", "WW_JP_Official", "Genshin_7", 
            "honkaistarrail", "lun_hong94850", "DarrenHung12", 
            "marika_vtuber", "index96703"
        ]
        self.settings_file = "otaku_settings.json"
        self.settings = self.load_settings()
        self.last_posts = {} # account: last_id
        self.twitter_loop.start()

    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as f:
                return json.load(f)
        return {"ww": None, "blue_archive": None, "general": None}

    def save_settings(self):
        with open(self.settings_file, 'w') as f:
            json.dump(self.settings, f)

    def cog_unload(self):
        self.twitter_loop.cancel()

    @commands.command(name="ww")
    async def set_ww(self, ctx):
        self.settings["ww"] = ctx.channel.id
        self.save_settings()
        await ctx.send(f"✅ **鳴潮 (WW_JP_Official)** 監控已綁定至此頻道！")

    @commands.command(name="蔚藍")
    async def set_ba(self, ctx):
        self.settings["blue_archive"] = ctx.channel.id
        self.save_settings()
        await ctx.send(f"✅ **蔚藍檔案 (EN_BlueArchive)** 監控已綁定至此頻道！")

    @commands.command(name="肥宅日常")
    async def set_general(self, ctx):
        self.settings["general"] = ctx.channel.id
        self.save_settings()
        await ctx.send(f"✅ **其餘大佬與遊戲動態** 監控已綁定至此頻道！")

    @tasks.loop(minutes=5)
    async def twitter_loop(self):
        nitter_instances = ["https://nitter.net", "https://nitter.it", "https://nitter.privacydev.net"]
        
        async with aiohttp.ClientSession() as session:
            for account in self.monitored_x:
                try:
                    # 決定目標頻道
                    target_id = self.settings["general"]
                    if account == "WW_JP_Official": target_id = self.settings["ww"]
                    elif account == "EN_BlueArchive": target_id = self.settings["blue_archive"]
                    
                    if not target_id: continue
                    channel = self.bot.get_channel(target_id)
                    if not channel: continue

                    instance = nitter_instances[0] 
                    async with session.get(f"{instance}/{account}/rss") as resp:
                        if resp.status == 200:
                            from xml.etree import ElementTree as ET
                            text = await resp.text()
                            root = ET.fromstring(text)
                            
                            items = root.findall(".//item")
                            if not items: continue
                            
                            latest = items[0]
                            post_id = latest.find("guid").text
                            title = latest.find("title").text
                            link = latest.find("link").text.replace("nitter.net", "x.com")
                            
                            if account not in self.last_posts:
                                self.last_posts[account] = post_id
                                continue
                                
                            if post_id != self.last_posts[account]:
                                self.last_posts[account] = post_id
                                embed = discord.Embed(
                                    title=f"📢 {account} 更新了！",
                                    description=title,
                                    url=link,
                                    color=0x1DA1F2,
                                    timestamp=datetime.utcnow()
                                )
                                embed.set_footer(text="優卡洛 ‧ 肥宅監控衛星")
                                await channel.send(embed=embed)
                except Exception as e:
                    print(f"❌ 監控 {account} 失敗: {e}")
                await asyncio.sleep(2)

    @commands.command(name="rbx")
    async def roblox_profile(self, ctx, username: str):
        async with aiohttp.ClientSession() as session:
            # 1. 獲取 User ID
            async with session.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [username]}) as resp:
                data = await resp.json()
                if not data.get("data"):
                    return await ctx.send("❌ 找不到這個 Roblox 玩家！")
                user_id = data["data"][0]["id"]
                display_name = data["data"][0]["displayName"]

            # 2. 獲取詳細資訊
            async with session.get(f"https://users.roblox.com/v1/users/{user_id}") as resp:
                info = await resp.json()
            
            # 3. 獲取頭像
            async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false") as resp:
                thumb_data = await resp.json()
                avatar_url = thumb_data["data"][0]["imageUrl"] if thumb_data.get("data") else ""

            embed = discord.Embed(title=f"🎮 Roblox Profile: {display_name}", url=f"https://www.roblox.com/users/{user_id}/profile", color=0xff0000)
            embed.set_thumbnail(url=avatar_url)
            embed.add_field(name="ID", value=user_id, inline=True)
            embed.add_field(name="加入日期", value=info.get("created", "未知")[:10], inline=True)
            embed.add_field(name="簡介", value=info.get("description", "無")[:200], inline=False)
            await ctx.send(embed=embed)

    @commands.command(name="狀態")
    async def user_status(self, ctx, user_id: int = None):
        if not user_id: user_id = ctx.author.id
        
        domain = os.getenv("CUSTOM_DOMAIN", "yokaro.wayna1015.ccwu.cc")
        url = f"https://stat.{domain}/api/status/{user_id}"
        
        embed = discord.Embed(
            title="💎 純金打造 ‧ 雲端狀態櫥窗",
            description=f"已為使用者 <@{user_id}> 生成專屬 Liquid Gold 頁面！",
            url=url,
            color=0xbf953f
        )
        embed.set_image(url="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndnBxeXN5emh6Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z3Z4Z/giphy.gif")
        embed.add_field(name="🔗 專屬連結", value=f"[點我進入純金殿堂]({url})")
        embed.set_footer(text="實時同步活動、Spotify 與 Discord 狀態")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(OtakuCog(bot))
