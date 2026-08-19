"""
cogs/afk.py
AFK 系統 (Away From Keyboard)
用戶設定 AFK 狀態後，其他人 @ 他時會自動回覆 AFK 訊息。
指令：
  !afk [時間] [理由]      - 設定 AFK (例如: !afk 1h 睡覺了)
  !afk cancel            - 取消自己的 AFK 狀態
  !afk list              - 查看伺服器內所有 AFK 用戶
  !afk clear @用戶       - 清除指定用戶的 AFK (管理員)
"""

import discord
from discord.ext import commands
import json
import os
import re
from datetime import datetime, timedelta

AFK_FILE = "afk_data.json"


class AFKCog(commands.Cog):
    """AFK 系統 - 設定離開時狀態並自動回覆"""

    def __init__(self, bot):
        self.bot = bot
        self.afk_data = self._load_data()

    def _load_data(self):
        if os.path.exists(AFK_FILE):
            try:
                with open(AFK_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_data(self):
        with open(AFK_FILE, "w", encoding="utf-8") as f:
            json.dump(self.afk_data, f, ensure_ascii=False, indent=2)

    def _parse_duration(self, duration_str: str):
        """解析時間字串為秒數。支援: 30s, 5m, 2h, 1d, 永久"""
        duration_str = duration_str.strip().lower()
        if duration_str in ("永久", "permanent", "∞", "inf"):
            return None
        pattern = re.match(r'^(\d+)\s*([smhd])$', duration_str)
        if not pattern:
            return None
        value = int(pattern.group(1))
        unit = pattern.group(2)
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        return value * multipliers[unit]

    def _format_duration(self, seconds: int) -> str:
        """將秒數格式化為可讀字串"""
        if seconds is None:
            return "永久"
        if seconds >= 86400:
            return f"{seconds // 86400}天"
        elif seconds >= 3600:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}小時{m}分" if m else f"{h}小時"
        elif seconds >= 60:
            m = seconds // 60
            s = seconds % 60
            return f"{m}分{s}秒" if s else f"{m}分"
        return f"{seconds}秒"

    @commands.hybrid_command(name="afk", aliases=["離開"])
    async def afk(self, ctx, duration: str = None, *, reason: str = "暫時離開"):
        """設定自己的 AFK 狀態，例如 !afk 1h 睡覺了。"""
        guild_id = str(ctx.guild.id) if ctx.guild else "DM"
        user_id = str(ctx.author.id)
        duration_seconds = None
        if duration is not None:
            duration_seconds = self._parse_duration(duration)
            if duration_seconds is None or duration_seconds <= 0:
                await ctx.send("❌ 時間格式錯誤！請使用 `30s`、`5m`、`1h`、`1d` 或 `永久`。", ephemeral=True)
                return

        now = datetime.now()
        self.afk_data.setdefault(guild_id, {})[user_id] = {
            "reason": reason,
            "duration": self._format_duration(duration_seconds),
            "duration_seconds": duration_seconds,
            "set_at_timestamp": now.timestamp(),
            "expires_at": now.timestamp() + duration_seconds if duration_seconds else None,
        }
        self._save_data()

        try:
            if ctx.guild and not ctx.author.display_name.startswith("[AFK]"):
                await ctx.author.edit(nick=f"[AFK] {ctx.author.display_name}", reason="設定 AFK 狀態")
        except (discord.Forbidden, discord.HTTPException):
            pass

        await ctx.send(f"💤 {ctx.author.mention} 已設定 AFK 狀態！\n理由：{reason}\n持續：{self._format_duration(duration_seconds)}")


    @commands.hybrid_command(name="afk_cancel", aliases=["取消afk", "afkoff", "取消離開"])
    async def afk_cancel(self, ctx):
        """取消自己的 AFK 狀態"""
        guild_id = str(ctx.guild.id) if ctx.guild else "DM"
        user_id = str(ctx.author.id)
        if guild_id not in self.afk_data or user_id not in self.afk_data.get(guild_id, {}):
            await ctx.send("❌ 你目前沒有設定 AFK 狀態喔！", ephemeral=True)
            return
        del self.afk_data[guild_id][user_id]
        self._save_data()
        try:
            if ctx.guild and ctx.author.display_name.startswith("[AFK]"):
                original_nick = ctx.author.display_name.replace("[AFK] ", "", 1)
                await ctx.author.edit(nick=original_nick or None, reason="取消 AFK 狀態")
        except (discord.Forbidden, Exception):
            pass
        embed = discord.Embed(title="✅ AFK 狀態已取消", description=f"{ctx.author.mention} 已從 AFK 狀態恢復！", color=0x2ecc71)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="afk_list", aliases=["afk列表", "afklist"])
    async def afk_list(self, ctx):
        """列出伺服器內所有 AFK 用戶"""
        guild_id = str(ctx.guild.id) if ctx.guild else "DM"
        if guild_id not in self.afk_data or not self.afk_data.get(guild_id):
            await ctx.send("📭 目前沒有任何人設定 AFK 狀態。", ephemeral=True)
            return
        embed = discord.Embed(title="💤 伺服器內的 AFK 用戕", color=0x95a5a6)
        now = datetime.now()
        count = 0
        for uid, info in list(self.afk_data[guild_id].items()):
            if info.get("duration_seconds") is not None and info.get("expires_at"):
                if now.timestamp() > info["expires_at"]:
                    del self.afk_data[guild_id][uid]
                    self._save_data()
                    continue
            user = self.bot.get_user(int(uid))
            uname = user.display_name if user else f"ID: {uid}"
            embed.add_field(name=uname, value=f"理由：{info['reason']}\n持續：{info['duration']}\n設置：<t:{int(info['set_at_timestamp'])}>", inline=False)
            count += 1
        if count == 0:
            await ctx.send("📭 目前沒有任何人設定 AFK 狀態。", ephemeral=True)
            return
        embed.set_footer(text=f"共 {count} 人處於 AFK 狀態")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="afk_clear", aliases=["清除afk"])
    @commands.has_permissions(administrator=True)
    async def afk_clear(self, ctx, member: discord.Member):
        """管理員強制清除指定用戶的 AFK 狀態"""
        guild_id = str(ctx.guild.id) if ctx.guild else "DM"
        user_id = str(member.id)
        if guild_id not in self.afk_data or user_id not in self.afk_data.get(guild_id, {}):
            await ctx.send(f"❌ {member.mention} 目前沒有設定 AFK 狀態！", ephemeral=True)
            return
        del self.afk_data[guild_id][user_id]
        self._save_data()
        try:
            if member.display_name.startswith("[AFK]"):
                original_nick = member.display_name.replace("[AFK] ", "", 1)
                await member.edit(nick=original_nick or None, reason=f"管理員 {ctx.author.display_name} 清除 AFK")
        except (discord.Forbidden, Exception):
            pass
        await ctx.send(f"✅ 已清除了 {member.mention} 的 AFK 狀態！")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """監聽提及 AFK 用戶的訊息，自動回覆"""
        if not message.guild or message.author.bot:
            return
        guild_id = str(message.guild.id)
        if guild_id not in self.afk_data or not self.afk_data.get(guild_id):
            return
        now = datetime.now()
        afk_mentions = []
        expired_users = []
        for uid, info in list(self.afk_data[guild_id].items()):
            if info.get("duration_seconds") is not None and info.get("expires_at"):
                if now.timestamp() > info["expires_at"]:
                    expired_users.append(uid)
                    continue
            target_user = int(uid)
            if target_user in [u.id for u in message.mentions]:
                afk_mentions.append((uid, info))
        # 移除過期 AFK
        for uid in expired_users:
            del self.afk_data[guild_id][uid]
        if expired_users:
            self._save_data()
        # 回覆 AFK 訊息
        if afk_mentions:
            parts = []
            for uid, info in afk_mentions:
                user = self.bot.get_user(int(uid))
                um = user.mention if user else f"<@{uid}>"
                parts.append(f"💤 {um} 目前是 AFK 狀態\n> 理由：{info['reason']}\n> 持續：{info['duration']}")
            embed = discord.Embed(title="💤 AFK 通知", description="\n\n".join(parts), color=0x95a5a6)
            await message.channel.send(embed=embed, reference=message, mention_author=False)


async def setup(bot):
    await bot.add_cog(AFKCog(bot))
