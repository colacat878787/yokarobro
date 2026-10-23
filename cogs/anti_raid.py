"""
cogs/anti_raid.py
防突襲系統（Anti-Raid）
偵測短時間大量成員加入，自動套用「隔離觀察」身分組（禁止發言/連音），
管理員可透過按鈕一鍵踢除或還原被隔離的帳號。

指令：
  !antiraid             - 顯示狀態
  !antiraid on / off    - 開關
  !antiraid window <秒>  設定偵測時間窗（預設 30 秒）
  !antiraid limit <人數>  設定時間窗內多少人加入視為 raid（預設 5）
  !antiraid age <天>     加入帳號小於此天數就直接隔離（預設 0 = 不檢查）
資料存 data/antiraid.json。
"""

from collections import deque
from datetime import datetime, timedelta
import os
import time

import discord
from discord.ext import commands, tasks

from utils.data_store import DataStore, format_duration

ROLE_NAME = "🛡️ 隔離觀察"


class RaidAlertView(discord.ui.View):
    """raid 警報上的處置按鈕"""

    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    async def _suspect_members(self, guild: discord.Guild):
        cfg = self.cog.store.get(guild.id, {})
        suspects = list((cfg.get("suspects") or {}).keys())
        return [guild.get_member(int(uid)) for uid in suspects if guild.get_member(int(uid))]

    @discord.ui.button(label="還原全部", style=discord.ButtonStyle.green, emoji="✅")
    async def release(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 只有管理員可以操作。", ephemeral=True)
            return
        members = await self._suspect_members(interaction.guild)
        for member in members:
            try:
                await member.remove_roles(*[r for r in member.roles if r.name == ROLE_NAME])
            except (discord.Forbidden, discord.HTTPException):
                pass
        self.cog._clear_suspects(interaction.guild)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"✅ {interaction.user.mention} 已還原 **{len(members)}** 位隔離成員。")

    @discord.ui.button(label="全部踢出", style=discord.ButtonStyle.red, emoji="👢")
    async def kick_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 只有管理員可以操作。", ephemeral=True)
            return
        members = await self._suspect_members(interaction.guild)
        kicked = 0
        for member in members:
            try:
                await member.kick(reason="[antiraid] 管理員一鍵踢除 raid 帳號")
                kicked += 1
            except (discord.Forbidden, discord.HTTPException):
                pass
        self.cog._clear_suspects(interaction.guild)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"👢 {interaction.user.mention} 已踢出 **{kicked}** 位 raid 帳號。")


class AntiRaidCog(commands.Cog):
    """🛡️ 防突襲系統"""

    def __init__(self, bot):
        self.bot = bot
        self.store = DataStore("antiraid.json")
        self.joins = {}  # {guild_id: deque[timestamp]}（僅記憶體，重啟即清空）
        self.maintenance.start()

    def cog_unload(self):
        self.maintenance.cancel()

    def _defaults(self) -> dict:
        return {"enabled": True, "window": 30, "limit": 5, "age": 0,
                "raid_until": None, "suspects": {}, "role_id": None}

    def get_cfg(self, guild_id: int) -> dict:
        cfg = self.store.get(guild_id, {})
        return {**self._defaults(), **cfg}

    def _save(self, guild_id, cfg):
        self.store.set(guild_id, cfg)

    def _clear_suspects(self, guild: discord.Guild):
        cfg = self.get_cfg(guild.id)
        cfg["suspects"] = {}
        cfg["raid_until"] = None
        self._save(guild.id, cfg)

    # ===== 指令 =====
    @commands.group(name="antiraid", aliases=["防raid", "防突襲"], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def antiraid(self, ctx):
        """顯示防突襲狀態"""
        cfg = self.get_cfg(ctx.guild.id)
        active = cfg["raid_until"] and datetime.fromisoformat(cfg["raid_until"]) > datetime.now().astimezone()
        embed = discord.Embed(title="🛡️ 防突襲系統", color=0x2ECC71 if cfg["enabled"] else 0x95A5A6)
        embed.add_field(name="狀態", value="✅ 啟用中" if cfg["enabled"] else "❌ 關閉", inline=True)
        embed.add_field(name="偵測", value=f"{cfg['limit']} 人／{format_duration(cfg['window'])}", inline=True)
        embed.add_field(name="帳齡門檻", value=f"{cfg['age']} 天" if cfg["age"] else "不檢查", inline=True)
        embed.add_field(
            name="目前隔離人數",
            value=str(len(cfg.get("suspects") or {})),
            inline=True,
        )
        if active:
            embed.add_field(name="🚨 Raid 模式", value=f"進行中（至 {cfg['raid_until'][:16].replace('T', ' ')}）", inline=False)
        await ctx.send(embed=embed)

    @antiraid.command(name="on", aliases=["開啟"])
    async def antiraid_on(self, ctx):
        cfg = self.get_cfg(ctx.guild.id)
        cfg["enabled"] = True
        self._save(ctx.guild.id, cfg)
        await ctx.send("✅ 防突襲系統已**開啟**。")

    @antiraid.command(name="off", aliases=["關閉"])
    async def antiraid_off(self, ctx):
        cfg = self.get_cfg(ctx.guild.id)
        cfg["enabled"] = False
        self._save(ctx.guild.id, cfg)
        await ctx.send("✅ 防突襲系統已**關閉**。")

    @antiraid.command(name="window")
    async def antiraid_window(self, ctx, seconds: int):
        """設定偵測時間窗秒數：!antiraid window 30"""
        if not 5 <= seconds <= 600:
            await ctx.send("❌ 時間窗需在 5~600 秒之間。")
            return
        cfg = self.get_cfg(ctx.guild.id)
        cfg["window"] = seconds
        self._save(ctx.guild.id, cfg)
        await ctx.send(f"✅ 偵測時間窗設定為 **{seconds} 秒**。")

    @antiraid.command(name="limit")
    async def antiraid_limit(self, ctx, count: int):
        """設定幾人加入觸發：!antiraid limit 5"""
        if not 3 <= count <= 100:
            await ctx.send("❌ 人數設定需在 3~100 之間。")
            return
        cfg = self.get_cfg(ctx.guild.id)
        cfg["limit"] = count
        self._save(ctx.guild.id, cfg)
        await ctx.send(f"✅ 觸發門檻設定為 **{count}** 人。")

    @antiraid.command(name="age")
    async def antiraid_age(self, ctx, days: int):
        """帳號年齡門檻（天）：!antiraid age 7（0 = 不檢查）"""
        if not 0 <= days <= 365:
            await ctx.send("❌ 天數需在 0~365 之間。")
            return
        cfg = self.get_cfg(ctx.guild.id)
        cfg["age"] = days
        self._save(ctx.guild.id, cfg)
        if days == 0:
            await ctx.send("✅ 已關閉帳齡檢查。")
        else:
            await ctx.send(f"✅ 帳齡少於 **{days} 天** 的成員加入時將被隔離。")

    # ===== 主函數：新成員加入 =====
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = self.get_cfg(member.guild.id)
        if not cfg["enabled"]:
            return

        now = time.time()
        window = deque(ts for ts in self.joins.get(member.guild.id, deque()) if now - ts < cfg["window"])
        window.append(now)
        self.joins[member.guild.id] = window

        in_raid = cfg["raid_until"] and datetime.fromisoformat(cfg["raid_until"]) > datetime.now().astimezone()
        old_account = _account_age_days(member) < cfg["age"]

        triggered = len(window) >= cfg["limit"]
        should_quarantine = triggered or in_raid or old_account

        if not should_quarantine:
            return

        if triggered and not in_raid:
            # 第一次觸發：進入 raid 模式
            cfg["raid_until"] = (datetime.now().astimezone() + timedelta(minutes=15)).isoformat()
            role = await self._ensure_suspect_role(member.guild)
            cfg["role_id"] = role.id if role else None
            self._save(member.guild.id, cfg)
            await self._announce_raid(member.guild, len(window), cfg["window"])

        role = await self._ensure_suspect_role(member.guild)
        if role is None:
            return
        try:
            await member.add_roles(role, reason="[antiraid] 可疑加入，隔離觀察")
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[AntiRaid] 無法隔離 {member}: {e}")
            return
        suspects = cfg.get("suspects") or {}
        suspects[str(member.id)] = (datetime.now().astimezone() + timedelta(minutes=30)).isoformat()
        cfg["suspects"] = suspects
        self._save(member.guild.id, cfg)

    async def _ensure_suspect_role(self, guild: discord.Guild):
        cfg = self.get_cfg(guild.id)
        role_id = cfg.get("role_id")
        role = None
        if role_id:
            role = guild.get_role(int(role_id))
        if role is None:
            role = next((r for r in guild.roles if r.name == ROLE_NAME), None)
        if role is None:
            try:
                role = await guild.create_role(
                    name=ROLE_NAME,
                    color=discord.Color.dark_gray(),
                    reason="[antiraid] 自動建立隔離身分組",
                )
            except (discord.Forbidden, discord.HTTPException) as e:
                print(f"[AntiRaid] 建立隔離身分組失敗: {e}")
                return None
            # 一次封鎖全頻道發言/連語音
            for channel in guild.channels:
                try:
                    await channel.set_permissions(
                        role,
                        send_messages=False,
                        add_reactions=False,
                        connect=False,
                        create_public_threads=False,
                        reason="[antiraid] 隔離權限",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass
        cfg["role_id"] = role.id
        return role

    async def _announce_raid(self, guild, join_count: int, window_sec: int):
        channel = guild.system_channel
        if channel is None or not channel.permissions_for(guild.me).send_messages:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break
        if channel is None:
            return
        embed = discord.Embed(
            title="🚨 偵測到疑似 Raid！",
            description=(
                f"**{join_count}** 位成員在 **{format_duration(window_sec)}** 內加入！\n"
                "已將這些成員套用「**🛡️ 隔離觀察**」身分組（禁止發言與連音）。\n"
                "請管理員確認他們的身分後使用下方按鈕處置。"
            ),
            color=0xE74C3C,
        )
        try:
            await channel.send(embed=embed, view=RaidAlertView(self, guild.id))
        except (discord.Forbidden, discord.NotFound):
            pass

    # ===== 背景維護：解除到期的隔離 =====
    @tasks.loop(seconds=60)
    async def maintenance(self):
        now = datetime.now().astimezone()
        for guild_id_str in list(self.store.data.keys()):
            cfg = self.get_cfg(int(guild_id_str))
            guild = self.bot.get_guild(int(guild_id_str))
            if not guild:
                continue

            # raid 模式到期
            if cfg.get("raid_until"):
                if datetime.fromisoformat(cfg["raid_until"]) <= now:
                    cfg["raid_until"] = None
                    self._save(guild.id, cfg)

            # 隔離到期 → 移除身分組
            suspects = cfg.get("suspects") or {}
            if suspects:
                role_id = cfg.get("role_id")
                role = guild.get_role(int(role_id)) if role_id else None
                remaining = {}
                for uid, expire in suspects.items():
                    try:
                        still_active = datetime.fromisoformat(expire) > now
                    except Exception:
                        still_active = False
                    if still_active:
                        remaining[uid] = expire
                        continue
                    member = guild.get_member(int(uid))
                    if member and role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason="[antiraid] 隔離時間到，自動還原")
                        except (discord.Forbidden, discord.HTTPException):
                            remaining[uid] = expire  # 留待下次
                if len(remaining) != len(suspects):
                    cfg["suspects"] = remaining
                    self._save(guild.id, cfg)

    @maintenance.before_loop
    async def before_maintenance(self):
        await self.bot.wait_until_ready()


def _account_age_days(member: discord.Member) -> int:
    try:
        created = member.created_at
        from datetime import timezone
        now = datetime.now(timezone.utc)
        return (now - created).days
    except Exception:
        return 9999


async def setup(bot):
    await bot.add_cog(AntiRaidCog(bot))
