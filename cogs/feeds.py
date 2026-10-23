"""
cogs/feeds.py
YouTube 新片 / Twitch 開播通知系統
指令：
  !youtube <頻道連結|@handle>   - 追蹤 YouTube 頻道，新影片發到當前頻道
  !youtube 停止 <連結|名稱>      - 停止追蹤（不填參數 = 顯示清單）
  !twitch <帳號>               - 追蹤 Twitch 直播主，開播時通知當前頻道
  !twitch 停止 <帳號>           - 停止追蹤
資料存在 data/feeds.json，每 5 分鐘檢查一次。
YouTube 使用公開 RSS feed（免金鑰）；Twitch 使用 Helix API（需在 .env 設定
  TWITCH_CLIENT_ID 與 TWITCH_CLIENT_SECRET）。
"""

import asyncio
import re

import aiohttp
import discord
import feedparser
from discord.ext import commands, tasks

from utils.data_store import DataStore

YT_CHANNEL_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
YT_PLAYLIST_FEED = "https://www.youtube.com/feeds/videos.xml?playlist_id={pid}"


def _find_youtube_channel_id(link):
    """從各種 YouTube 連結/字串取出 UC 開頭的頻道 ID"""
    link = link.strip()
    # 直接就是 UC...
    m = re.search(r"(UC[\w-]{22})", link)
    if m:
        return m.group(1)
    # 上傳播放清單 UU...
    m = re.search(r"list=(UU[\w-]{20,})", link)
    if m:
        return m.group(1)
    return None


def _find_youtube_handle(link):
    """從 @handle 或 /@handle 連結取出 handle"""
    m = re.search(r"@([\w\-.]{3,30})", link)
    if m:
        return m.group(1)
    return None


class FeedCog(commands.Cog):
    """📺 YouTube / Twitch 通知系統"""

    def __init__(self, bot):
        self.bot = bot
        # {guild_id: [{"kind": "youtube"|"twitch", "key": 識別, "name": 顯示名,
        #              "channel_id": int, "last_id": str}]}
        self.store = DataStore("feeds.json")
        self.twitch_token = None
        self.check_feeds.start()

    def cog_unload(self):
        self.check_feeds.cancel()

    # ===== 指令 =====
    @commands.group(name="youtube", aliases=["yt", "追蹤yt"], invoke_without_command=True)
    @commands.guild_only()
    async def youtube(self, ctx, link: str = None):
        """追蹤 YouTube 頻道：!youtube <頻道連結>"""
        if link is None:
            await self._send_list(ctx, "youtube")
            return
        link = link.strip()

        channel_id = _find_youtube_channel_id(link)
        preview_name = None
        if channel_id:
            # 上傳播放清單（UU...）存原字串，頻道 ID（UC...）也存
            key = channel_id
        else:
            handle = _find_youtube_handle(link)
            if not handle:
                await ctx.send(
                    "❌ 無法解析 YouTube 頻道。\n支援格式：\n"
                    "• `https://www.youtube.com/channel/UCxxxxxx`\n"
                    "• `https://www.youtube.com/@handle`\n"
                    "• 頻道 ID（UC 開頭）"
                )
                return
            async with aiohttp.ClientSession() as session:
                preview_name = f"@{handle}"
                channel_id = await self._resolve_handle(session, handle)
                if not channel_id:
                    await ctx.send(
                        f"❌ 無法從 `@{handle}` 取得頻道 ID。\n"
                        "請改用 `!youtube <頻道 /channel/UCxxxx 連結>`。"
                    )
                    return
            key = f"@{handle}"

        configs = self.store.get(ctx.guild.id, [])
        for cfg in configs:
            if cfg["kind"] == "youtube" and cfg["key"] == key:
                cfg["channel_id"] = ctx.channel.id
                cfg["last_id"] = ""
                self.store.set(ctx.guild.id, configs)
                await ctx.send(f"✅ 已更新 **{preview_name or cfg['name']}** 的追蹤 → {ctx.channel.mention}")
                return

        feed_name = preview_name or key
        try:
            async with aiohttp.ClientSession() as session:
                feed_name = await self._fetch_feed_title(session, channel_id) or feed_name
        except Exception:
            pass
        configs.append({
            "kind": "youtube",
            "key": key,
            "name": feed_name,
            "yt_cid": channel_id,
            "channel_id": ctx.channel.id,
            "last_id": "",
        })
        self.store.set(ctx.guild.id, configs)
        await ctx.send(f"✅ 開始追蹤 YouTube 頻道 **{feed_name}**！新影片會發到這個頻道。")

    @youtube.command(name="stop", aliases=["停止", "off"])
    @commands.guild_only()
    async def youtube_stop(self, ctx, link: str = None):
        """停止追蹤：!youtube 停止 <連結|頻道名稱>"""
        await self._stop(ctx, "youtube", link)

    @commands.group(name="twitch", aliases=["追蹤twitch"], invoke_without_command=True)
    @commands.guild_only()
    async def twitch(self, ctx, login: str = None):
        """追蹤 Twitch 直播主：!twitch <帳號>"""
        if login is None:
            await self._send_list(ctx, "twitch")
            return
        if not self._twitch_ready():
            await ctx.send(
                "❌ 需要 Twitch API 金鑰！請管理者在 `.env` 加入：\n"
                "`TWITCH_CLIENT_ID=你的Client_ID`\n`TWITCH_CLIENT_SECRET=你的Client_Secret`\n"
                "（到 https://dev.twitch.tv/console 建立 App 即可取得）"
            )
            return
        login = login.strip().lstrip("@").lower()
        if not re.match(r"^[A-Za-z0-9_]{3,25}$", login):
            await ctx.send("❌ 無效的 Twitch 帳號名稱。")
            return

        configs = self.store.get(ctx.guild.id, [])
        for cfg in configs:
            if cfg["kind"] == "twitch" and cfg["key"].lower() == login:
                cfg["channel_id"] = ctx.channel.id
                cfg["last_id"] = ""
                self.store.set(ctx.guild.id, configs)
                await ctx.send(f"✅ 已更新 **{cfg['name']}** 的追蹤 → {ctx.channel.mention}")
                return

        display, uid = await self._twitch_user_info(login)
        if not uid:
            await ctx.send(f"❌ 找不到 Twitch 帳號 `{login}`。")
            return
        configs.append({
            "kind": "twitch",
            "key": login,
            "name": display,
            "channel_id": ctx.channel.id,
            "last_id": "",
        })
        self.store.set(ctx.guild.id, configs)
        await ctx.send(f"✅ 開始追蹤 Twitch **{display}**！開播時會通知這個頻道。")

    @twitch.command(name="stop", aliases=["停止", "off"])
    @commands.guild_only()
    async def twitch_stop(self, ctx, login: str = None):
        """停止追蹤：!twitch 停止 <帳號>"""
        await self._stop(ctx, "twitch", login)

    # ===== 內部 helper =====
    async def _send_list(self, ctx, kind):
        configs = [c for c in self.store.get(ctx.guild.id, []) if c["kind"] == kind]
        if not configs:
            await ctx.send(f"📋 這個伺服器還沒有追蹤任何 {'YouTube' if kind == 'youtube' else 'Twitch'} 來源。")
            return
        lines = [f"• **{c['name']}** → <#{c['channel_id']}>" for c in configs]
        embed = discord.Embed(
            title=f"📋 追蹤中的 {'YouTube 頻道' if kind == 'youtube' else 'Twitch 直播主'}",
            description="\n".join(lines),
            color=0xFF0000 if kind == "youtube" else 0x9146FF,
        )
        await ctx.send(embed=embed)

    async def _stop(self, ctx, kind, ident):
        configs = self.store.get(ctx.guild.id, [])
        ident = (ident or "").strip().lstrip("@")
        if not ident:
            await self._send_list(ctx, kind)
            return
        target = _find_youtube_channel_id(ident) or ident if kind == "youtube" else ident

        def match(cfg):
            if cfg["kind"] != kind:
                return False
            return (target.lower() in (cfg["key"].lower(), cfg["name"].lower(),
                                       (cfg.get("yt_cid") or "").lower())
                    or (kind == "twitch" and cfg["key"].lower() == target.lower()))

        configs = [c for c in configs if not match(c)]
        self.store.set(ctx.guild.id, configs)
        await ctx.send(f"✅ 已停止追蹤 `{ident}`。")

    async def _resolve_handle(self, session, handle: str):
        """從 @handle 頁面 HTML 抓 channel_id（best-effort）"""
        url = f"https://www.youtube.com/@{handle}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; FuwawaBot/1.0)"}
        try:
            async with session.get(url, timeout=15, headers=headers) as r:
                if r.status != 200:
                    return None
                html = await r.text()
            m = re.search(r'"(?:externalChannelId|channelId)":"(UC[\w-]{22})"', html)
            if m:
                return m.group(1)
            m = re.search(r"youtube\.com/channel/(UC[\w-]{22})", html)
            return m.group(1) if m else None
        except Exception:
            return None

    async def _fetch_feed_title(self, session, channel_key):
        if channel_key.startswith("UU"):
            url = YT_PLAYLIST_FEED.format(pid=channel_key)
        else:
            url = YT_CHANNEL_FEED.format(cid=channel_key)
        try:
            async with session.get(url, timeout=15) as r:
                if r.status != 200:
                    return None
                feed = feedparser.parse(await r.text())
            if feed.feed.get("title"):
                # feed title 通常是 "XXX - Videos"
                return str(feed.feed.title).replace(" - Videos", "")
        except Exception:
            pass
        return None

    # ===== Twitch =====
    def _twitch_ready(self):
        import os
        return bool(os.getenv("TWITCH_CLIENT_ID") and os.getenv("TWITCH_CLIENT_SECRET"))

    async def _get_twitch_token(self):
        import os
        client_id = os.getenv("TWITCH_CLIENT_ID")
        client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params, timeout=15) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                return data.get("access_token")

    async def _api(self, url: str, **kwargs):
        """帶 token 呼叫 Twitch helix API，401 時自動刷新一次"""
        import os
        client_id = os.getenv("TWITCH_CLIENT_ID")
        headers = {"Client-ID": client_id}
        if self.twitch_token:
            headers["Authorization"] = f"Bearer {self.twitch_token}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15, **kwargs) as r:
                if r.status == 401 and not kwargs.get("retry"):
                    self.twitch_token = await self._get_twitch_token()
                    if self.twitch_token:
                        headers["Authorization"] = f"Bearer {self.twitch_token}"
                        async with session.get(url, headers=headers, timeout=15) as r2:
                            if r2.status == 200:
                                return await r2.json()
                    return None
                if r.status == 200:
                    return await r.json()
        return None

    async def _twitch_user_info(self, login: str):
        if not self.twitch_token:
            self.twitch_token = await self._get_twitch_token()
        data = await self._api(f"https://api.twitch.tv/helix/users?login={login}")
        users = (data or {}).get("data", [])
        if not users:
            return None, None
        return users[0].get("display_name", login), users[0].get("id")

    # ===== 主輪詢 =====
    @tasks.loop(minutes=5)
    async def check_feeds(self):
        if not self.store.data:
            return
        try:
            async with aiohttp.ClientSession() as session:
                # Twitch：先預熱 token（有追蹤任何 twitch 才需要）
                need_twitch = any(
                    any(c["kind"] == "twitch" for c in self.store.get(gid, []))
                    for gid in list(self.store.data.keys())
                )
                if need_twitch and not self.twitch_token:
                    self.twitch_token = await self._get_twitch_token()

                for guild_id_str in list(self.store.data.keys()):
                    guild_id = int(guild_id_str)
                    configs = self.store.get(guild_id, [])
                    for cfg in list(configs):
                        try:
                            if cfg["kind"] == "youtube":
                                await self._check_youtube(session, guild_id, cfg)
                            elif cfg["kind"] == "twitch":
                                await self._check_twitch(guild_id, cfg)
                        except Exception as e:
                            print(f"Feed check error ({cfg['name']}): {e}")
                        await asyncio.sleep(2)
        except Exception as e:
            print(f"Feeds loop error: {e}")

    async def _check_youtube(self, session, guild_id, cfg):
        key = cfg["key"]
        cid = key if key.startswith(("UC", "UU")) else cfg.get("yt_cid")
        if cid is None:
            cid = await self._resolve_handle(session, key.lstrip("@"))
            if cid:
                cfg["yt_cid"] = cid
                self.store.set(guild_id, self.store.get(guild_id, []))
        if not cid:
            return
        if cid.startswith("UU"):
            url = YT_PLAYLIST_FEED.format(pid=cid)
        else:
            url = YT_CHANNEL_FEED.format(cid=cid)
        channel = self.bot.get_channel(cfg["channel_id"])
        if channel is None:
            return
        try:
            async with session.get(url, timeout=15) as r:
                if r.status != 200:
                    return
                feed = feedparser.parse(await r.text())
        except Exception:
            return
        if not feed.entries:
            return
        entry = feed.entries[0]
        video_id = getattr(entry, "yt_videoid", None)
        if not video_id:
            video_id = re.sub(r"^yt:video:", "", getattr(entry, "id", "")) or None
        if str(video_id) == cfg.get("last_id"):
            return
        was_new = bool(cfg.get("last_id"))
        cfg["last_id"] = str(video_id or "")
        self.store.set(guild_id, self.store.get(guild_id, []))

        if not was_new:
            return  # 第一次追蹤不回報舊片

        embed = discord.Embed(
            title=entry.title,
            url=entry.link,
            description=(getattr(entry, "description", "") or "")[:180],
            color=0xFF0000,
        )
        thumb = getattr(entry, "media_thumbnail", None)
        if thumb:
            embed.set_image(url=thumb[0].get("url"))
        author = getattr(feed.feed, "title", cfg["name"])
        embed.set_author(name=f"🆕 {str(author).replace(' - Videos', '')} 上傳新影片！")
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.NotFound):
            pass

    async def _check_twitch(self, guild_id, cfg):
        if not self.twitch_token:
            return
        channel = self.bot.get_channel(cfg["channel_id"])
        if channel is None:
            return
        data = await self._api(
            f"https://api.twitch.tv/helix/streams?user_login={cfg['key']}"
        )
        streams = (data or {}).get("data", [])
        stream_id = streams[0].get("id") if streams else ""
        if stream_id == cfg.get("last_id"):
            return
        cfg["last_id"] = stream_id
        self.store.set(guild_id, self.store.get(guild_id, []))
        if not stream_id or not streams:
            return  # 下播，靜默

        s = streams[0]
        embed = discord.Embed(
            title=s.get("title") or "（無標題）",
            url=f"https://www.twitch.tv/{cfg['key']}",
            color=0x9146FF,
        )
        embed.set_author(name=f"🔴 {cfg['name']} 開播了！")
        embed.add_field(name="🎮 遊戲", value=s.get("game_name", "未知") or "未知", inline=True)
        embed.add_field(name="👀 觀眾", value=str(s.get("viewer_count", 0)), inline=True)
        thumb = s.get("thumbnail_url", "").replace("{width}", "1280").replace("{height}", "720")
        if thumb:
            embed.set_image(url=thumb)
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.NotFound):
            pass

    @check_feeds.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(FeedCog(bot))
