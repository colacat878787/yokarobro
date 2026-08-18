"""
cogs/alarm.py
鬧鐘系統 (Alarm)
設定鬧鐘並選擇提醒頻率，時間到時在該頻道連續發送提醒訊息。
指令：
  !鬧鐘 <時間> <原因>   - 設定鬧鐘並透過選單選擇頻率 (例如: !鬧鐘 16:30 洗澡)
  !鬧鐘 off <時間>       - 取消指定時間的鬧鐘
  !鬧鐘 list             - 列出本頻道的鬧鐘
"""

import discord
from discord.ext import commands, tasks
import json
import os
import re
import asyncio
from datetime import datetime, date

ALARM_FILE = "alarms.json"
MSGS = 5  # 每次響鈴發送的訊息次數

# 頻率預設
PRESETS = {
    "today": {"type": "today", "label": "只有今日", "desc": "只提醒今天一次"},
    "daily": {"type": "daily", "label": "每天", "desc": "每天這個時間提醒"},
    "135": {"type": "weekdays", "days": [0, 2, 4], "label": "一三五", "desc": "每週一、三、五"},
    "246": {"type": "weekdays", "days": [1, 3, 5], "label": "二四六", "desc": "每週二、四、六"},
    "sun": {"type": "weekdays", "days": [6], "label": "星期日", "desc": "每週日"},
}
WEEKDAY_NAMES = ["一", "二", "三", "四", "五", "六", "日"]


class AlarmScheduleSelect(discord.ui.Select):
    """選擇提醒頻率的下拉選單"""

    def __init__(self, view):
        self.view = view
        options = [
            discord.SelectOption(label=p["label"], value=k, description=p["desc"])
            for k, p in PRESETS.items()
        ]
        super().__init__(placeholder="選擇提醒頻率...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction):
        self.view.selected = self.values[0]
        await self.view.update_embed(interaction)


class AlarmSetupView(discord.ui.View):
    """鬧鐘設定選單 (選擇頻率 + 設定完成)"""

    def __init__(self, cog, time_str, reason, user_id):
        super().__init__(timeout=120)
        self.cog = cog
        self.time_str = time_str
        self.reason = reason
        self.user_id = user_id
        self.selected = "daily"  # 預設每天
        self.add_item(AlarmScheduleSelect(self))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有設定鬧鐘的人可以操作！", ephemeral=True)
            return False
        return True

    async def update_embed(self, interaction):
        preset = PRESETS.get(self.selected, PRESETS["daily"])
        embed = discord.Embed(title="⏰ 鬧鐘設定", color=0x2ecc71)
        embed.add_field(name="🕐 時間", value=f"**{self.time_str}**", inline=True)
        embed.add_field(name="📝 原因", value=self.reason, inline=True)
        embed.add_field(name="🔁 頻率", value=preset["label"], inline=False)
        embed.set_footer(text="選擇頻率後點擊「設定完成」")
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="✅ 設定完成", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        preset = PRESETS.get(self.selected, PRESETS["daily"])
        schedule = {
            "type": preset["type"],
            "days": preset.get("days", []),
            "label": preset["label"],
        }
        target_date = None
        if schedule["type"] == "today":
            target_date = date.today().isoformat()

        gid = str(interaction.guild.id)
        cid = str(interaction.channel.id)
        if gid not in self.cog.alarms:
            self.cog.alarms[gid] = {}
        if cid not in self.cog.alarms[gid]:
            self.cog.alarms[gid][cid] = []

        for a in self.cog.alarms[gid][cid]:
            if a.get("time") == self.time_str:
                await interaction.response.send_message(f"❌ 本頻道已經有 `{self.time_str}` 的鬧鐘了！使用 `!鬧鐘 list` 查看。", ephemeral=True)
                return

        self.cog.alarms[gid][cid].append({
            "time": self.time_str,
            "reason": self.reason,
            "user_id": self.user_id,
            "last_fired": None,
            "schedule": schedule,
            "target_date": target_date,
        })
        self.cog._save_alarms()

        embed = discord.Embed(title="✅ 鬧鐘設定完成", color=0x2ecc71)
        embed.add_field(name="🕐 時間", value=f"**{self.time_str}**", inline=True)
        embed.add_field(name="📝 原因", value=self.reason, inline=True)
        embed.add_field(name="🔁 頻率", value=preset["label"], inline=False)
        embed.add_field(name="📍 頻道", value=interaction.channel.mention, inline=False)
        embed.set_footer(text=f"到了 {self.time_str} 我會在這裡提醒你 {MSGS} 次喔！")
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class AlarmCog(commands.Cog):
    """鬧鐘系統 - 定時提醒"""

    def __init__(self, bot):
        self.bot = bot
        self.alarms = self._load_alarms()
        self.check_alarms.start()

    def _load_alarms(self):
        if os.path.exists(ALARM_FILE):
            try:
                with open(ALARM_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_alarms(self):
        with open(ALARM_FILE, "w", encoding="utf-8") as f:
            json.dump(self.alarms, f, ensure_ascii=False, indent=2)

    def cog_unload(self):
        self.check_alarms.cancel()

    def _should_fire(self, alarm, today_str, today_weekday):
        """判斷鬧鐘今天是否該響"""
        sched = alarm.get("schedule") or {"type": "daily"}
        stype = sched.get("type", "daily")

        if stype == "today":
            return alarm.get("target_date") == today_str

        if stype == "weekdays":
            return today_weekday in sched.get("days", [])

        # daily 每天
        return True

    @tasks.loop(seconds=1)
    async def check_alarms(self):
        """每秒檢查鬧鐘是否到點 (確保準時)"""
        now = datetime.now()
        cur_time = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")
        today_weekday = now.weekday()
        fired_any = False

        for guild_id, channels in list(self.alarms.items()):
            guild = self.bot.get_guild(int(guild_id))
            if not guild or not isinstance(channels, dict):
                continue
            for channel_id, alarm_list in list(channels.items()):
                if not isinstance(alarm_list, list):
                    continue
                channel = guild.get_channel(int(channel_id))
                if not channel:
                    continue
                remaining = []
                for alarm in alarm_list:
                    if alarm.get("time") == cur_time and alarm.get("last_fired") != today_str:
                        if self._should_fire(alarm, today_str, today_weekday):
                            alarm["last_fired"] = today_str
                            fired_any = True
                            await self._fire(channel, alarm)
                            sched = alarm.get("schedule") or {}
                            if sched.get("type") == "today":
                                continue
                    remaining.append(alarm)
                channels[channel_id] = remaining

        if fired_any:
            self._save_alarms()

    async def _fire(self, channel, alarm):
        """發送鬧鐘提醒訊息 (連續發 5 次)"""
        user_id = alarm.get("user_id")
        reason = alarm.get("reason") or "起床"
        user = self.bot.get_user(int(user_id)) if user_id else None
        mention = user.mention if user else f"<@{user_id}>"
        text = f"{mention} 您該{reason}了!! By.幽芙優Yofuyu"
        for _ in range(MSGS):
            try:
                await channel.send(text)
                await asyncio.sleep(0.5)
            except discord.Forbidden:
                break

    def _parse_time(self, time_str):
        """解析 HH:MM 時間格式"""
        m = re.match(r"^(\d{1,2})[:：](\d{2})$", time_str.strip())
        if not m:
            return None
        h, minute = int(m.group(1)), int(m.group(2))
        if h > 23 or minute > 59:
            return None
        return f"{h:02d}:{minute:02d}"

    @commands.group(name="鬧鐘", aliases=["alarm"], invoke_without_command=True)
    async def alarm(self, ctx, time_str: str = None, *, reason: str = None):
        """設定鬧鐘 - 例如: !鬧鐘 16:30 洗澡 (會跳出頻率選單)"""
        if time_str is None:
            await ctx.send("❓ 請指定時間！例如：`!鬧鐘 16:30 洗澡`", ephemeral=True)
            return
        parsed = self._parse_time(time_str)
        if parsed is None:
            await ctx.send("❌ 時間格式錯誤！請使用 `HH:MM` 格式，例如 `!鬧鐘 16:30 洗澡`", ephemeral=True)
            return
        if not reason:
            reason = "起床"

        embed = discord.Embed(title="⏰ 鬧鐘設定", color=0x2ecc71)
        embed.add_field(name="🕐 時間", value=f"**{parsed}**", inline=True)
        embed.add_field(name="📝 原因", value=reason, inline=True)
        embed.add_field(name="🔁 頻率", value="每天（請選擇你要的頻率）", inline=False)
        embed.set_footer(text="從下方選單選擇提醒頻率，完成後點擊「設定完成」")

        view = AlarmSetupView(self, parsed, reason, ctx.author.id)
        await ctx.send(embed=embed, view=view)

    @alarm.command(name="off", aliases=["取消", "刪除"])
    async def alarm_off(self, ctx, time_str: str):
        """取消指定時間的鬧鐘"""
        parsed = self._parse_time(time_str)
        if parsed is None:
            await ctx.send("❌ 時間格式錯誤！請使用 `HH:MM` 格式。", ephemeral=True)
            return
        gid = str(ctx.guild.id)
        cid = str(ctx.channel.id)
        lst = self.alarms.get(gid, {}).get(cid, [])
        for i, a in enumerate(lst):
            if a.get("time") == parsed:
                if a.get("user_id") != ctx.author.id and not ctx.author.guild_permissions.administrator:
                    await ctx.send("❌ 只有設定鬧鐘的人或管理員可以取消！", ephemeral=True)
                    return
                del lst[i]
                self._save_alarms()
                await ctx.send(f"✅ 已取消 `{parsed}` 的鬧鐘！")
                return
        await ctx.send(f"❌ 本頻道沒有 `{parsed}` 的鬧鐘。", ephemeral=True)

    @alarm.command(name="list", aliases=["列表"])
    async def alarm_list(self, ctx):
        """列出本頻道的所有鬧鐘"""
        gid = str(ctx.guild.id)
        cid = str(ctx.channel.id)
        lst = self.alarms.get(gid, {}).get(cid, [])
        if not lst:
            await ctx.send("📭 本頻道沒有設定任何鬧鐘。", ephemeral=True)
            return
        embed = discord.Embed(title="⏰ 本頻道鬧鐘列表", color=0x3498db)
        for a in lst:
            user = self.bot.get_user(a.get("user_id", 0))
            uname = user.display_name if user else f"ID:{a.get('user_id')}"
            sched = a.get("schedule") or {}
            freq = sched.get("label", "每天")
            embed.add_field(
                name=f"🕐 {a['time']} · {freq}",
                value=f"📝 {a.get('reason')}\n👤 {uname}",
                inline=True
            )
        embed.set_footer(text="使用 !鬧鐘 off <時間> 來取消")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AlarmCog(bot))
