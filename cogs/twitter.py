import discord
from discord.ext import commands, tasks
import feedparser
import aiohttp
import os
import asyncio
import re
from utils.i18n import t
from utils.data_store import DataStore

# 公開 Nitter 實例列表 (若掛掉請自行更換)
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.cz",
    "https://nitter.it",
    "https://nitter.privacydev.net"
]


def parse_username(link: str):
    """從 X/Twitter 個人檔案連結、@username 或純帳號名中解析出使用者名稱"""
    link = link.strip()
    if not link:
        return None
    # @username
    m = re.search(r"@([A-Za-z0-9_]{1,15})$", link)
    if m:
        return m.group(1)
    # x.com/username 或 twitter.com/username
    m = re.search(r"(?:twitter|x)\.com/([A-Za-z0-9_]{1,15})", link)
    if m:
        return m.group(1)
    # 純帳號名
    if re.match(r"^[A-Za-z0-9_]{1,15}$", link):
        return link
    return None


class TwitterCog(commands.Cog):
    """🐦 X/Twitter 貼文頻道系統 - !twitter <個人檔案連結>"""

    def __init__(self, bot):
        self.bot = bot
        self.store = DataStore("twitter.json")  # {guild_id: [{username, channel_id, last_post}]}
        self.check_twitter.start()

    def cog_unload(self):
        self.check_twitter.cancel()

    def get_configs(self, guild_id):
        return self.store.get(guild_id, [])

    def commit(self, guild_id, configs):
        self.store.set(guild_id, configs)

    @commands.command(name='twitter', aliases=['推特頻道', 'xfeed', '追蹤貼文'])
    async def twitter(self, ctx, link: str):
        """把當前頻道變成指定 X/Twitter 帳號的貼文頻道：!twitter <個人檔案連結>"""
        if ctx.guild is None:
            return await ctx.send("❌ 此指令只能在伺服器中使用！")

        username = parse_username(link)
        if not username:
            return await ctx.send(t(ctx.guild.id, "twitter.invalid"))

        configs = self.get_configs(ctx.guild.id)
        for cfg in configs:
            if cfg["username"].lower() == username.lower():
                cfg["channel_id"] = ctx.channel.id  # 更新到當前頻道
                self.commit(ctx.guild.id, configs)
                return await ctx.send(t(ctx.guild.id, "twitter.updated", user=username))

        configs.append({"username": username, "channel_id": ctx.channel.id, "last_post": ""})
        self.commit(ctx.guild.id, configs)
        await ctx.send(t(ctx.guild.id, "twitter.tracked", user=username))

    @commands.command(name='twitterstop', aliases=['停止推特頻道', 'xstop'])
    async def twitter_stop(self, ctx, link: str):
        """停止指定 X/Twitter 帳號的貼文頻道：!twitterstop <個人檔案連結>"""
        if ctx.guild is None:
            return await ctx.send("❌ 此指令只能在伺服器中使用！")

        username = parse_username(link)
        if not username:
            return await ctx.send(t(ctx.guild.id, "twitter.invalid"))

        configs = self.get_configs(ctx.guild.id)
        new_configs = [c for c in configs if c["username"].lower() != username.lower()]
        if len(new_configs) == len(configs):
            return await ctx.send(t(ctx.guild.id, "twitter.notfound", user=username))

        self.commit(ctx.guild.id, new_configs)
        await ctx.send(t(ctx.guild.id, "twitter.stopped", user=username))

    @tasks.loop(minutes=5)  # 每 5 分鐘檢查一次，避免被封 IP
    async def check_twitter(self):
        if not self.store.data:
            return
        try:
            async with aiohttp.ClientSession() as session:
                # 遍歷每個伺服器的每個設定
                for guild_id_str in list(self.store.data.keys()):
                    guild_id = int(guild_id_str)
                    configs = self.get_configs(guild_id)
                    for cfg in list(configs):
                        await self._check_user(session, guild_id, cfg)
                        await asyncio.sleep(2)  # 每個帳號間隔 2 秒，防被禁
        except Exception as e:
            print(f"Twitter loop error: {e}")

    async def _check_user(self, session, guild_id, cfg):
        """檢查單一帳號是否有新貼文，並發送到其對應頻道"""
        username = cfg["username"]
        channel = self.bot.get_channel(cfg["channel_id"])
        if not channel:
            return

        for instance in NITTER_INSTANCES:
            rss_url = f"{instance}/{username}/rss"
            try:
                async with session.get(rss_url, timeout=10) as response:
                    if response.status != 200:
                        continue
                    content = await response.text()
                    feed = feedparser.parse(content)
                    if not feed.entries:
                        continue
                    latest = feed.entries[0]
                    link = latest.link

                    if cfg.get("last_post") != link:
                        cfg["last_post"] = link
                        self._persist_cfg(guild_id, username, cfg)

                        real_link = link.replace(instance, "https://twitter.com")
                        description = (latest.description or "")[:200]
                        if description:
                            description += "..."

                        embed = discord.Embed(
                            title=t(guild_id, "twitter.new", user=username),
                            description=description,
                            url=real_link,
                            color=0x1da1f2,
                        )
                        embed.set_footer(text=t(guild_id, "twitter.footer"))
                        await channel.send(embed=embed)
                    return  # 成功取得該帳號最新貼文，結束
            except Exception as e:
                print(f"Twitter check error for {username} ({instance}): {e}")
                await asyncio.sleep(1)
        print(f"Twitter: all Nitter instances failed for {username}")

    def _persist_cfg(self, guild_id, username, cfg):
        """更新單一帳號的 last_post 並寫回儲存"""
        configs = self.get_configs(guild_id)
        for c in configs:
            if c["username"].lower() == username.lower():
                c["last_post"] = cfg["last_post"]
                break
        self.commit(guild_id, configs)

    @check_twitter.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(TwitterCog(bot))

