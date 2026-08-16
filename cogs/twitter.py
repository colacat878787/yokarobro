import discord
from discord.ext import commands, tasks
import feedparser
import aiohttp
import os
import asyncio
import re
from utils.i18n import t
from utils.data_store import DataStore

# 公開 RSSHub 實例（主要來源，免費免登入）
RSSHUB_INSTANCES = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://rsshub.pseudoyu.com",
]

# 公開 Nitter 實例（備援，Nitter 已大量失效）
NITTER_INSTANCES = [
    "https://xcancel.com",
    "https://nitter.catsarch.com",
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
        """檢查單一帳號是否有新貼文，依序嘗試 RSSHub → Nitter"""
        username = cfg["username"]
        channel = self.bot.get_channel(cfg["channel_id"])
        if not channel:
            return

        # 依序嘗試所有來源
        sources = []
        for inst in RSSHUB_INSTANCES:
            sources.append((inst, f"{inst}/twitter/user/{username}", "rsshub"))
        for inst in NITTER_INSTANCES:
            sources.append((inst, f"{inst}/{username}/rss", "nitter"))

        for instance, rss_url, src in sources:
            try:
                async with session.get(rss_url, timeout=15) as response:
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

                        real_link = self._clean_tweet_link(link, instance, src)
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
                    return  # 成功取得該帳號最新貼文
            except Exception as e:
                print(f"Twitter check error for {username} ({instance}, {src}): {e}")
                await asyncio.sleep(1)
        print(f"Twitter: all sources failed for {username}")

    @staticmethod
    def _clean_tweet_link(link, instance, src):
        """將 feed 連結轉換為可直接點擊的 twitter.com 連結"""
        if src == "rsshub":
            # RSSHub 的連結通常是真實的 twitter.com URL
            if link.startswith(instance):
                link = link.replace(instance, "")
            if "twitter.com" not in link:
                # 可能是相對路徑，拼接為完整連結
                link = f"https://twitter.com{link}" if link.startswith("/") else f"https://twitter.com/{link}"
            if not link.startswith("http"):
                link = "https://twitter.com/" + link.lstrip("/")
            return link
        # nitter: 取代 nitter 實例為 twitter.com
        return link.replace(instance, "https://twitter.com")

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

