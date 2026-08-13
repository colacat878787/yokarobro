import discord
from discord.ext import commands
import asyncio
import json
import os
import re
from datetime import datetime
import aiohttp
from utils.i18n import t

YT_COUNTDOWN_FILE = "yt_countdown_data.json"


class YTCountdownData:
    """YouTube subscriber countdown data management"""

    def __init__(self):
        self.countdowns = {}
        self._load()

    def _load(self):
        if os.path.exists(YT_COUNTDOWN_FILE):
            try:
                with open(YT_COUNTDOWN_FILE, "r", encoding="utf-8") as f:
                    self.countdowns = json.load(f)
            except:
                pass

    def _save(self):
        with open(YT_COUNTDOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(self.countdowns, f, ensure_ascii=False, indent=2)

    def add_countdown(self, guild_id, channel_id, yt_channel, target_count):
        gid = str(guild_id)
        cid = str(channel_id)
        if gid not in self.countdowns:
            self.countdowns[gid] = {}
        self.countdowns[gid][cid] = {
            "yt_channel": yt_channel,
            "target": target_count,
            "last_count": 0,
            "message_id": None,
            "started_at": datetime.now().isoformat(),
        }
        self._save()
        return True

    def remove_countdown(self, guild_id, channel_id):
        gid = str(guild_id)
        cid = str(channel_id)
        if gid in self.countdowns and cid in self.countdowns[gid]:
            del self.countdowns[gid][cid]
            if not self.countdowns[gid]:
                del self.countdowns[gid]
            self._save()
            return True
        return False

    def get_countdown(self, guild_id, channel_id):
        gid = str(guild_id)
        cid = str(channel_id)
        if gid in self.countdowns and cid in self.countdowns[gid]:
            return self.countdowns[gid][cid]
        return None

    def get_all_countdowns(self):
        all_countdowns = []
        for gid, channels in self.countdowns.items():
            for cid, data in channels.items():
                all_countdowns.append(
                    {"guild_id": int(gid), "channel_id": int(cid), **data}
                )
        return all_countdowns

    def update_last_count(self, guild_id, channel_id, count):
        gid = str(guild_id)
        cid = str(channel_id)
        if gid in self.countdowns and cid in self.countdowns[gid]:
            self.countdowns[gid][cid]["last_count"] = count
            self._save()


class YTSubCountdownCog(commands.Cog):
    """YouTube Subscriber Countdown"""

    def __init__(self, bot):
        self.bot = bot
        self.data = YTCountdownData()
        self.countdown_task = None
        self.session = None

    async def cog_load(self):
        """Start background task when cog loads"""
        self.session = aiohttp.ClientSession()
        self.countdown_task = self.bot.loop.create_task(self._countdown_loop())
        print("✅ YouTube subscriber countdown system started")

    async def cog_unload(self):
        """Clean up when cog unloads"""
        if self.countdown_task:
            self.countdown_task.cancel()
        if self.session:
            await self.session.close()

    async def _countdown_loop(self):
        """Background task: check subscriber count every 1 second"""
        await self.bot.wait_until_ready()
        print("🔄 YouTube subscriber count check loop started")

        while not self.bot.is_closed():
            try:
                countdowns = self.data.get_all_countdowns()
                for cd in countdowns:
                    await self._check_subscriber_count(cd)
            except Exception as e:
                print(f"Subscriber check error: {e}")

            await asyncio.sleep(1)

        print("🛑 YouTube subscriber count check loop stopped")

    async def _check_subscriber_count(self, countdown_data):
        """Check subscriber count for a single channel"""
        guild_id = countdown_data["guild_id"]
        channel_id = countdown_data["channel_id"]
        yt_channel = countdown_data["yt_channel"]
        target = countdown_data["target"]
        last_count = countdown_data["last_count"]

        current_count = await self._fetch_subscriber_count(yt_channel)
        if current_count is None:
            return

        if last_count == 0:
            self.data.update_last_count(guild_id, channel_id, current_count)
            return

        if current_count != last_count:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return

            channel = guild.get_channel(channel_id)
            if not channel:
                return

            diff = current_count - last_count
            if diff > 0:
                emoji = "📈"
                diff_str = f"+{diff:,}"
                color = 0xff0000
            else:
                emoji = "📉"
                diff_str = f"{diff:,}"
                color = 0x00ff00

            embed = discord.Embed(
                title=t(guild_id, "yt.change.title", emoji=emoji),
                description=f"**{yt_channel}**\n"
                            f"{t(guild_id, 'yt.change.from', old=last_count, new=current_count)}\n"
                            f"{t(guild_id, 'yt.change.diff', diff=diff_str)}",
                color=color,
                timestamp=datetime.now(),
            )
            embed.set_thumbnail(url="https://www.youtube.com/s/desktop/946b7c58/img/favicon_144x144.png")

            try:
                await channel.send(embed=embed)
            except:
                pass

            if current_count >= target:
                celebration_embed = discord.Embed(
                    title=t(guild_id, "yt.celebrate.title"),
                    description=t(guild_id, "yt.celebrate.desc"),
                    color=0xffd700,
                    timestamp=datetime.now(),
                )
                celebration_embed.set_thumbnail(url="https://www.youtube.com/s/desktop/946b7c58/img/favicon_144x144.png")
                celebration_embed.set_footer(text="🎆")
                # 用正確參數重建慶祝訊息
                celebration_embed.description = t(
                    guild_id, "yt.celebrate.desc",
                    channel=yt_channel, target=target, current=current_count,
                )

                try:
                    await channel.send(embed=celebration_embed)
                except:
                    pass

                self.data.remove_countdown(guild_id, channel_id)
                return

            self.data.update_last_count(guild_id, channel_id, current_count)

    async def _fetch_subscriber_count(self, channel_identifier):
        """Fetch subscriber count using non-official methods"""
        try:
            # Method 1: Use yt-dlp (阻塞呼叫移到背景執行緒，避免卡住 event loop)
            try:
                import yt_dlp

                def _blocking_fetch():
                    with yt_dlp.YoutubeDL({
                        "quiet": True,
                        "no_warnings": True,
                        "extract_flat": True,
                    }) as ydl:
                        info = ydl.extract_info(
                            f"https://www.youtube.com/{channel_identifier}",
                            download=False,
                        )
                        if info and "channel_follower_count" in info:
                            return info["channel_follower_count"]
                    return None

                count = await asyncio.to_thread(_blocking_fetch)
                if count:
                    return count
            except ImportError:
                pass

            # Method 2: Web scraping
            channel_url = f"https://www.youtube.com/{channel_identifier}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            async with self.session.get(
                channel_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    return None

                html = await response.text()

                patterns = [
                    r'"subscriberCountText":\{"runs":\[\{"text":"([^"]+)"\}\],',
                    r'"subscriberCount":"([^"]+)"',
                ]

                for pattern in patterns:
                    match = re.search(pattern, html)
                    if match:
                        count_str = match.group(1)
                        count_str = (
                            count_str.replace("位訂閱者", "")
                            .replace(" subscribers", "")
                            .strip()
                        )
                        return self._parse_count(count_str)

                match = re.search(
                    r"var ytInitialData = ({.*?});</script>", html, re.DOTALL
                )
                if match:
                    try:
                        data = json.loads(match.group(1))
                        subscriber_count = self._extract_from_yt_data(data)
                        if subscriber_count:
                            return subscriber_count
                    except:
                        pass

            return None

        except Exception as e:
            print(f"Failed to fetch subscriber count: {e}")
            return None

    def _parse_count(self, count_str):
        """Parse subscriber count string (e.g., 1.23M, 456K)"""
        count_str = count_str.lower().replace(",", "").replace(" ", "")

        multipliers = {
            "k": 1000,
            "m": 1000000,
            "b": 1000000000,
            "萬": 10000,
            "億": 100000000,
        }

        for suffix, multiplier in multipliers.items():
            if count_str.endswith(suffix):
                number = float(count_str[: -len(suffix)])
                return int(number * multiplier)

        try:
            return int(count_str)
        except:
            return None

    def _extract_from_yt_data(self, data):
        """Extract subscriber count from YouTube initial data"""
        try:
            if isinstance(data, dict):
                for key, value in data.items():
                    if "subscriber" in key.lower() and isinstance(value, (str, int)):
                        return self._parse_count(str(value))
                    elif isinstance(value, (dict, list)):
                        result = self._extract_from_yt_data(value)
                        if result:
                            return result
            elif isinstance(data, list):
                for item in data:
                    result = self._extract_from_yt_data(item)
                    if result:
                        return result
        except:
            pass
        return None

    @commands.command(name="ytsubcountdown", aliases=["yt訂閱倒數", "訂閱倒數"])
    async def start_countdown(self, ctx, channel_link: str, target_count: int):
        """
        Start YouTube subscriber countdown

        Usage:
        !ytsubcountdown <YT channel link or username> <target subscriber count>

        Examples:
        !ytsubcountdown @MrBeast 100000000
        !ytsubcountdown https://www.youtube.com/@MrBeast 100000000
        !ytsubcountdown MrBeast 100000000
        """
        if target_count <= 0:
            return await ctx.send(t(ctx.guild.id, "yt.target.invalid"))

        if target_count > 1000000000:
            return await ctx.send(t(ctx.guild.id, "yt.target.too_high"))

        channel_identifier = self._extract_channel_identifier(channel_link)
        if not channel_identifier:
            return await ctx.send(
                t(ctx.guild.id, "yt.channel.invalid") + "\n"
                "• `!ytsubcountdown @username 1000000`\n"
                "• `!ytsubcountdown https://www.youtube.com/@username 1000000`"
            )

        await ctx.send(t(ctx.guild.id, "yt.testing"))
        current_count = await self._fetch_subscriber_count(channel_identifier)

        if current_count is None:
            return await ctx.send(t(ctx.guild.id, "yt.fetch_fail"))

        existing = self.data.get_countdown(ctx.guild.id, ctx.channel.id)
        if existing:
            return await ctx.send(
                f"{t(ctx.guild.id, 'yt.already_tracking', channel=existing['yt_channel'])}\n"
                f"{t(ctx.guild.id, 'yt.status.target', target=existing['target'])}\n"
                f"{t(ctx.guild.id, 'yt.status.current', current=existing['last_count'])}\n"
                f"`!ytsubstop` / `!停止訂閱倒數`"
            )

        if current_count >= target_count:
            return await ctx.send(
                t(ctx.guild.id, "yt.already_target", channel=channel_identifier, target=target_count)
            )

        self.data.add_countdown(ctx.guild.id, ctx.channel.id, channel_identifier, target_count)

        embed = discord.Embed(
            title=t(ctx.guild.id, "yt.started.title"),
            description=(
                f"{t(ctx.guild.id, 'yt.started.channel', channel=channel_identifier)}\n"
                f"{t(ctx.guild.id, 'yt.started.target', target=target_count)}\n"
                f"{t(ctx.guild.id, 'yt.started.current', current=current_count)}\n"
                f"{t(ctx.guild.id, 'yt.started.remaining', remaining=target_count - current_count)}\n\n"
                f"{t(ctx.guild.id, 'yt.started.check')}\n"
                f"{t(ctx.guild.id, 'yt.started.notify')}\n"
                f"{t(ctx.guild.id, 'yt.started.celebrate')}"
            ),
            color=0xff0000,
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url="https://www.youtube.com/s/desktop/946b7c58/img/favicon_144x144.png")
        embed.set_footer(text=t(ctx.guild.id, "yt.started.footer"))

        msg = await ctx.send(embed=embed)
        self.data.countdowns[str(ctx.guild.id)][str(ctx.channel.id)]["message_id"] = msg.id

    @commands.command(name="ytsubstop", aliases=["停止訂閱倒數", "ytstop"])
    async def stop_countdown(self, ctx):
        """Stop the YouTube subscriber countdown in this channel"""
        result = self.data.remove_countdown(ctx.guild.id, ctx.channel.id)

        if result:
            embed = discord.Embed(
                title=t(ctx.guild.id, "yt.stop.title"),
                description=t(ctx.guild.id, "yt.stop.desc"),
                color=0x95a5a6,
                timestamp=datetime.now(),
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(t(ctx.guild.id, "yt.no_active"))

    @commands.command(name="ytsubstatus", aliases=["訂閱狀態", "ytstatus"])
    async def countdown_status(self, ctx):
        """Check the current subscriber countdown status"""
        countdown = self.data.get_countdown(ctx.guild.id, ctx.channel.id)

        if not countdown:
            return await ctx.send(
                t(ctx.guild.id, "yt.no_active") + "\n"
                "`!ytsubcountdown <channel> <target>`"
            )

        current_count = await self._fetch_subscriber_count(countdown["yt_channel"])
        if current_count:
            self.data.update_last_count(ctx.guild.id, ctx.channel.id, current_count)

        target = countdown["target"]
        current = current_count if current_count else countdown["last_count"]
        remaining = target - current
        progress = (current / target * 100) if target > 0 else 0

        progress_bar = self._create_progress_bar(progress)

        embed = discord.Embed(
            title=t(ctx.guild.id, "yt.status.title"),
            description=(
                f"**{countdown['yt_channel']}**\n\n"
                f"{t(ctx.guild.id, 'yt.status.target', target=target)}\n"
                f"{t(ctx.guild.id, 'yt.status.current', current=current)}\n"
                f"{t(ctx.guild.id, 'yt.status.remaining', remaining=remaining)}\n"
                f"{t(ctx.guild.id, 'yt.status.progress', progress=progress)}\n\n"
                f"{progress_bar}"
            ),
            color=0x00ff00 if current >= target else 0xffaa00,
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url="https://www.youtube.com/s/desktop/946b7c58/img/favicon_144x144.png")

        await ctx.send(embed=embed)

    def _extract_channel_identifier(self, input_str):
        """Extract YouTube channel identifier from input"""
        input_str = input_str.strip()

        if input_str.startswith("http"):
            patterns = [
                r"youtube\.com/@([^/?]+)",
                r"youtube\.com/channel/([^/?]+)",
                r"youtube\.com/c/([^/?]+)",
                r"youtube\.com/user/([^/?]+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, input_str)
                if match:
                    return match.group(1)

        if input_str.startswith("@"):
            return input_str

        return input_str

    def _create_progress_bar(self, percentage, length=20):
        """Create a visual progress bar"""
        filled = int(length * percentage / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"`{bar}` {percentage:.1f}%"


async def setup(bot):
    await bot.add_cog(YTSubCountdownCog(bot))



