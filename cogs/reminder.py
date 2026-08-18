"""
cogs/reminder.py
提醒系統 (Reminders)
 lets users set timed reminders.
指令：
  !remindme <時間> <訊息>  - 設定提醒 (例如: !remindme 1h 去喝水)
  !remindme list          - 列出自己的提醒
  !remindme cancel <ID>   - 取消提醒
"""

import discord
from discord.ext import commands, tasks
import json
import os
import re
from datetime import datetime, timedelta

REMINDER_FILE = "reminders.json"


def parse_reminder_time(time_str: str):
    """解析提醒時間字串。支援: 30s, 5m, 2h, 1d 或完整格式如 1h30m"""
    time_str = time_str.strip().lower()
    total_seconds = 0
    pattern = re.findall(r'(\d+)([smhd])', time_str)
    if not pattern:
        return None
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    for value, unit in pattern:
        total_seconds += int(value) * multipliers[unit]
    return total_seconds if total_seconds > 0 else None


def format_reminder_time(seconds: int) -> str:
    """將秒數格式化為可讀字串"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds // 60}分{seconds % 60}秒" if seconds % 60 else f"{seconds // 60}分"
    elif seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}小時{m}分" if m else f"{h}小時"
    else:
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        return f"{d}天{h}小時" if h else f"{d}天"


class ReminderCog(commands.Cog):
    """提醒系統 - 設定定時提醒"""

    def __init__(self, bot):
        self.bot = bot
        self.reminders = self._load_reminders()
        self.check_reminders.start()

    def _load_reminders(self):
        if os.path.exists(REMINDER_FILE):
            try:
                with open(REMINDER_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_reminders(self):
        with open(REMINDER_FILE, "w", encoding="utf-8") as f:
            json.dump(self.reminders, f, ensure_ascii=False, indent=2)

    def cog_unload(self):
        self.check_reminders.cancel()

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        """背景任務：檢查並發送到時的提醒"""
        now = datetime.now().timestamp()
        due_ids = []
        for rid, data in list(self.reminders.items()):
            if now >= data["expires_at"]:
                due_ids.append(rid)
                try:
                    user = await self.bot.fetch_user(data["user_id"])
                    channel = self.bot.get_channel(data.get("channel_id", 0))
                    msg = data["message"]
                    if channel:
                        embed = discord.Embed(title="⏰ 提醒", description=msg, color=0xf1c40f)
                        embed.set_footer(text="提醒時間到囉！")
                        await channel.send(content=f"{user.mention}，你的提醒到了！", embed=embed)
                    else:
                        embed = discord.Embed(title="⏰ 提醒", description=msg, color=0xf1c40f)
                        embed.set_footer(text="提醒時間到囉！")
                        await user.send(embed=embed)
                except Exception as e:
                    print(f"[Reminder] 發送提醒失敗: {e}")
        for rid in due_ids:
            del self.reminders[rid]
        if due_ids:
            self._save_reminders()

    @commands.hybrid_group(name="remindme", aliases=["提醒", "reminder"], invoke_without_command=True)
    async def remindme(self, ctx, time_str: str = None, *, message: str = None):
        """設定提醒 - 例如: !remindme 1h 去喝水"""
        if time_str is None:
            await ctx.send("❓ 請指定時間和訊息！\n範例：`!remindme 1h 去喝水`\n支援單位：`30s`、`5m`、`2h`、`1d`", ephemeral=True)
            return
        seconds = parse_reminder_time(time_str)
        if seconds is None:
            await ctx.send("❌ 時間格式錯誤！請使用：`30s`、`5m`、`2h`、`1d` 或組合如 `1h30m`", ephemeral=True)
            return
        if seconds > 31536000:
            await ctx.send("❌ 提醒時間不能超過 1 年喔！", ephemeral=True)
            return
        if message is None:
            message = f"提醒：{format_reminder_time(seconds)} 後"

        now = datetime.now()
        expires_at = now + timedelta(seconds=seconds)
        reminder_id = str(len(self.reminders) + 1)
        while reminder_id in self.reminders:
            reminder_id = str(int(reminder_id) + 1)

        self.reminders[reminder_id] = {
            "user_id": ctx.author.id,
            "guild_id": str(ctx.guild.id) if ctx.guild else None,
            "channel_id": ctx.channel.id if ctx.guild else None,
            "message": message,
            "expires_at": expires_at.timestamp(),
            "set_at": now.timestamp(),
            "duration": seconds
        }
        self._save_reminders()

        embed = discord.Embed(title="✅ 提醒已設定", color=0x3498db)
        embed.add_field(name="⏰ 響應時間", value=format_reminder_time(seconds), inline=True)
        embed.add_field(name="📅 到期時間", value=f"<t:{int(expires_at.timestamp())}:R>", inline=True)
        embed.add_field(name="📝 提醒內容", value=message, inline=False)
        embed.add_field(name="🆔 提醒 ID", value=reminder_id, inline=True)
        embed.set_footer(text="使用 !提醒 list 查看你的提醒")
        await ctx.send(f"{ctx.author.mention} 設定好了！⏰", embed=embed)

    @remindme.command(name="list", aliases=["列表"])
    async def remindme_list(self, ctx):
        """列出自己的提醒"""
        user_id = ctx.author.id
        user_reminders = [(rid, data) for rid, data in self.reminders.items() if data["user_id"] == user_id]
        if not user_reminders:
            await ctx.send("📭 你沒有任何進行中的提醒。", ephemeral=True)
            return
        embed = discord.Embed(title="📋 你的提醒列表", color=0x3498db)
        now = datetime.now().timestamp()
        for rid, data in user_reminders:
            remaining = data["expires_at"] - now
            remaining_str = "即將到來" if remaining <= 0 else format_reminder_time(int(remaining))
            embed.add_field(
                name=f"#{rid} - {data['message'][:50]}",
                value=f"⏱️ 剩餘：{remaining_str}\n📅 到期：<t:{int(data['expires_at'])}:R>",
                inline=False
            )
        embed.set_footer(text=f"共 {len(user_reminders)} 個提醒")
        await ctx.send(embed=embed)

    @remindme.command(name="cancel", aliases=["取消"])
    async def remindme_cancel(self, ctx, reminder_id: str = None):
        """取消提醒"""
        if reminder_id is None:
            await ctx.send("❓ 請指定要取消的提醒 ID。\n使用 `!提醒 list` 查看你的提醒 ID。", ephemeral=True)
            return
        user_id = ctx.author.id
        if reminder_id not in self.reminders:
            await ctx.send(f"❌ 找不到 ID 為 `{reminder_id}` 的提醒！", ephemeral=True)
            return
        data = self.reminders[reminder_id]
        if data["user_id"] != user_id:
            await ctx.send("❌ 這不是你的提醒，你不能取消別人的提醒喔！", ephemeral=True)
            return
        msg_preview = data["message"][:50]
        del self.reminders[reminder_id]
        self._save_reminders()
        await ctx.send(f"✅ 已取消提醒 #{reminder_id}：「{msg_preview}」")


async def setup(bot):
    await bot.add_cog(ReminderCog(bot))
