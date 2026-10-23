"""
cogs/temp_punish.py
限時懲罰系統（持久化資料，重啟不失效）
指令：
  !tempmute <時間> <成員> [理由] - 限時禁言（使用 Discord 原生 timeout）
  !unmute <成員>                - 解除禁言
  !tempban <時間> <成員|ID> [理由] - 限時封禁（時間到自動解除）
  !untempban <成員|ID>          - 取消排程中的解封
  !tempbans                     - 查看待解封名單
時間格式支援：30s / 5m / 2h / 1d / 1w / 1h30m
"""

import discord
from discord.ext import commands, tasks
from datetime import timedelta

from utils.data_store import DataStore, format_duration


def _member_or_uid(member_arg: str):
    """把參數解析為使用者 ID（int）或 None"""
    arg = member_arg.strip()
    if arg.startswith("<@") and arg.endswith(">"):
        inner = arg[2:-1].lstrip("!")
        if inner.isdigit():
            return int(inner)
        return None
    return int(arg) if arg.isdigit() else None


class TempPunishCog(commands.Cog):
    """⏳ 限時懲罰系統 - tempmute / tempban"""

    def __init__(self, bot):
        self.bot = bot
        # {guild_id: {"bans": [{"user_id": int, "unban_at": iso, "reason": str, "mod_id": int}]}}
        self.store = DataStore("temp_punish.json")
        self.check_tempbans.start()

    def cog_unload(self):
        self.check_tempbans.cancel()

    # ===== 限時禁言 =====
    @commands.command(name="tempmute", aliases=["限時禁言", "暫時禁言"])
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def tempmute(self, ctx, duration: str, member: discord.Member, *, reason: str = "無提供理由"):
        """限時禁言：!tempmute <時間> <成員> [理由]"""
        seconds = self._parse_seconds(duration)
        if seconds is None:
            await ctx.send("❌ 無法解析時間。範例：`!tempmute 30m @小美 刷屏`、`!tempmute 1h30m @小美`")
            return
        if member.bot:
            await ctx.send("❌ 不能禁言機器人！")
            return
        if member.top_role >= ctx.author.top_role and not ctx.guild.owner_id == ctx.author.id:
            await ctx.send("❌ 你不能禁言職位比你高或相同的成員！")
            return

        # Discord timeout 上限 28 天
        seconds = min(seconds, 28 * 86400)
        until = discord.utils.utcnow() + timedelta(seconds=seconds)
        try:
            await member.timeout(until, reason=f"[tempmute by {ctx.author}] {reason}")
        except (discord.Forbidden, discord.HTTPException) as e:
            await ctx.send(f"❌ 禁言失敗：{e}")
            return

        embed = discord.Embed(
            title="⏳ 已限時禁言",
            color=0xE67E22,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 成員", value=f"{member.mention}（{member}）", inline=True)
        embed.add_field(name="⏱️ 時長", value=format_duration(seconds), inline=True)
        embed.add_field(name="📄 理由", value=reason[:1024], inline=False)
        embed.add_field(name="🧑‍⚖️ 執行", value=ctx.author.mention, inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="unmute", aliases=["解除禁言"])
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        """解除禁言：!unmute <成員>"""
        until = getattr(member, "timed_out_until", None)
        if not until:
            await ctx.send("❌ 這個成員目前沒有被禁言。")
            return
        try:
            await member.timeout(None, reason=f"[unmute by {ctx.author}]")
        except (discord.Forbidden, discord.HTTPException) as e:
            await ctx.send(f"❌ 解除禁言失敗：{e}")
            return
        await ctx.send(f"✅ 已解除 {member.mention} 的禁言。")

    # ===== 限時封禁 =====
    @commands.command(name="tempban", aliases=["限時封禁", "暫時封禁"])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def tempban(self, ctx, duration: str, target: str, *, reason: str = "無提供理由"):
        """限時封禁：!tempban <時間> <成員|ID> [理由]（時間到自動解封）"""
        seconds = self._parse_seconds(duration)
        if seconds is None:
            await ctx.send("❌ 無法解析時間。範例：`!tempban 1d @小美 挑釁`、`!tempban 3d 123456789`")
            return

        # 解析目標（可為成員或 ID）
        user_id = None
        user_name = str(target)
        user_avatar = None
        if isinstance(target, str):
            user_id = _member_or_uid(target)
        if user_id is None:
            try:
                conv = commands.MemberConverter()
                m = await conv.convert(ctx, target)
                user_id, user_name = m.id, str(m)
                user_avatar = m.display_avatar.url
            except commands.CommandError:
                await ctx.send("❌ 無法解析目標成員。請直接 @ 成員或使用使用者 ID。")
                return
        else:
            try:
                user = await self.bot.fetch_user(user_id)
                user_name, user_avatar = str(user), user.display_avatar.url
            except discord.HTTPException:
                pass

        guild = ctx.guild
        member = guild.get_member(user_id)
        if member and member.top_role >= ctx.author.top_role and ctx.guild.owner_id != ctx.author.id:
            await ctx.send("❌ 你不能封禁職位比你高或相同的成員！")
            return
        try:
            await guild.ban(
                discord.Object(id=user_id),
                reason=f"[tempban by {ctx.author}] {reason}",
                delete_message_seconds=0,
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            await ctx.send(f"❌ 封禁失敗：{e}")
            return

        # 記錄到排程（isoformat 存檔）
        unban_at = (discord.utils.utcnow() + timedelta(seconds=seconds)).isoformat()
        guild_cfg = self.store.get(guild.id, {"bans": []})
        guild_cfg.setdefault("bans", [])
        already = any(b["user_id"] == user_id for b in guild_cfg["bans"])
        if not already:
            guild_cfg["bans"].append({"user_id": user_id, "unban_at": unban_at, "reason": reason})
        else:
            for b in guild_cfg["bans"]:
                if b["user_id"] == user_id:
                    b["unban_at"] = unban_at
                    b["reason"] = reason
        self.store.set(guild.id, guild_cfg)

        embed = discord.Embed(title="⏳ 已限時封禁", color=0xE74C3C)
        if user_avatar:
            embed.set_thumbnail(url=user_avatar)
        embed.add_field(name="👤 成員", value=f"<@{user_id}>（{user_name}）", inline=True)
        embed.add_field(name="⏱️ 時長", value=format_duration(seconds), inline=True)
        embed.add_field(name="📄 理由", value=reason[:1024], inline=False)
        embed.add_field(name="🧑‍⚖️ 執行", value=ctx.author.mention, inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="untempban", aliases=["取消封禁"])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def untempban(self, ctx, target: str):
        """取消排程中的自動解封：!untempban <成員|ID>"""
        user_id = _member_or_uid(target)
        if user_id is None:
            await ctx.send("❌ 請提供成員或使用者 ID。")
            return
        guild_cfg = self.store.get(ctx.guild.id, {"bans": []})
        before = len(guild_cfg.get("bans", []))
        guild_cfg["bans"] = [b for b in guild_cfg.get("bans", []) if b["user_id"] != user_id]
        self.store.set(ctx.guild.id, guild_cfg)
        if len(guild_cfg["bans"]) < before:
            await ctx.send(f"✅ 已取消 <@{user_id}> 的排程解封。")
        else:
            await ctx.send(f"❌ 找不到 <@{user_id}> 的排程解封記錄。")

    @commands.command(name="tempbans", aliases=["限時封禁清單"])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def tempbans(self, ctx):
        """查看待解封名單：!tempbans"""
        guild_cfg = self.store.get(ctx.guild.id, {"bans": []})
        bans = sorted(guild_cfg.get("bans", []), key=lambda b: b.get("unban_at", ""))
        if not bans:
            await ctx.send("📋 目前沒有限時封禁的記錄。")
            return
        lines = []
        for b in bans[:20]:
            lines.append(f"• <@{b['user_id']}> — 解封：{b.get('unban_at', '?')[:16].replace('T', ' ')}｜理由：{b.get('reason', '')[:40]}")
        embed = discord.Embed(title="📋 限時封禁名單", color=0xE74C3C, description="\n".join(lines))
        await ctx.send(embed=embed)

    # ===== 排程解封任務 =====
    @tasks.loop(seconds=60)
    async def check_tempbans(self):
        now = discord.utils.utcnow()
        for guild_id_str in list(self.store.data.keys()):
            guild_cfg = self.store.get(guild_id_str, {"bans": []})
            bans = guild_cfg.get("bans", [])
            if not bans:
                continue
            guild = self.bot.get_guild(int(guild_id_str))
            if not guild:
                continue
            remaining = []
            changed = False
            for b in bans:
                try:
                    expire = discord.utils.parse_time(b["unban_at"])
                except Exception:
                    expire = None
                if expire is None or expire > now:
                    remaining.append(b)
                    continue
                try:
                    await guild.unban(discord.Object(id=b["user_id"]), reason="[tempban] 開封時間到，自動解封")
                    print(f"✅ [TempPunish] 已自動解封 {b['user_id']} @ {guild.name}")
                except discord.NotFound:
                    pass  # 已經被解了
                except discord.Forbidden:
                    remaining.append(b)  # 沒權限，留到下次
                    continue
                changed = True
            if changed or len(remaining) != len(bans):
                guild_cfg["bans"] = remaining
                self.store.set(guild_id_str, guild_cfg)

    @check_tempbans.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def _parse_seconds(s: str):
        from utils.data_store import parse_duration
        seconds = parse_duration(s)
        if seconds <= 0 and str(s).isdigit():
            seconds = int(s)  # 給純數字當秒數
        return seconds if seconds > 0 else None


async def setup(bot):
    await bot.add_cog(TempPunishCog(bot))
