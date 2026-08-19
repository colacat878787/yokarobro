"""
cogs/alarm.py
鬧鐘系統 (Alarm) - 互動式面板
使用 !鬧鐘 會彈出面板，可新增或取消鬧鐘，並選擇提醒頻率。
到點時在該頻道連續發送提醒訊息。
"""

import discord
from discord.ext import commands, tasks
import json
import os
import re
import asyncio
from datetime import datetime, date

ALARM_FILE = "alarms.json"
MSGS = 5

PRESETS = {
    "today": {"type": "today", "label": "只有今日", "desc": "只提醒今天一次"},
    "daily": {"type": "daily", "label": "每天", "desc": "每天這個時間提醒"},
    "135": {"type": "weekdays", "days": [0, 2, 4], "label": "一三五", "desc": "每週一、三、五"},
    "246": {"type": "weekdays", "days": [1, 3, 5], "label": "二四六", "desc": "每週二、四、六"},
    "sun": {"type": "weekdays", "days": [6], "label": "星期日", "desc": "每週日"},
}


def parse_time_str(time_str):
    """解析 HH:MM 格式為字串"""
    m = re.match(r"^(\d{1,2})[:：](\d{2})$", time_str.strip())
    if not m:
        return None
    h, minute = int(m.group(1)), int(m.group(2))
    if h > 23 or minute > 59:
        return None
    return f"{h:02d}:{minute:02d}"


class AlarmPanelView(discord.ui.View):
    """!鬧鐘 主面板：顯示鬧鐘 + 新增/取消/重新整理/關閉"""

    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        self.message = None

    def build_embed(self, channel_id):
        gid = str(self.cog._current_guild_id)
        lst = self.cog.alarms.get(gid, {}).get(str(channel_id), [])
        embed = discord.Embed(title="⏰ 優卡洛鬧鐘面板", color=0x2ecc71)
        embed.description = "點擊下方按鈕來新增或取消鬧鐘。"
        if lst:
            desc_lines = []
            for i, a in enumerate(lst, 1):
                sched = a.get("schedule") or {}
                freq = sched.get("label", "每天")
                user = self.cog.bot.get_user(a.get("user_id", 0))
                uname = user.display_name if user else "?"
                desc_lines.append(f"{i}. `{a['time']}` · {freq} · 📝 {a.get('reason')} · 👤 {uname}")
            embed.add_field(name=f"📋 目前鬧鐘 ({len(lst)})", value="\n".join(desc_lines), inline=False)
        else:
            embed.add_field(name="📭 尚無鬧鐘", value="目前本頻道沒有任何鬧鐘，點「➕ 新增鬧鐘」開始設定！", inline=False)
        embed.set_footer(text="鬧鐘到點會連續提醒 5 次")
        return embed

    @discord.ui.button(label="➕ 新增鬧鐘", style=discord.ButtonStyle.success, row=0)
    async def add_btn(self, interaction, button):
        await interaction.response.send_modal(AlarmAddModal(self.cog))

    @discord.ui.button(label="🗑️ 取消鬧鐘", style=discord.ButtonStyle.danger, row=0)
    async def cancel_btn(self, interaction, button):
        gid = str(interaction.guild.id)
        lst = self.cog.alarms.get(gid, {}).get(str(interaction.channel.id), [])
        if not lst:
            return await interaction.response.send_message("📭 目前沒有鬧鐘可以取消！", ephemeral=True)
        await interaction.response.send_message(
            "選擇要取消的鬧鐘：",
            view=AlarmDeleteView(self.cog, interaction.guild.id, interaction.channel.id),
            ephemeral=True,
        )

    @discord.ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_btn(self, interaction, button):
        self.cog._current_guild_id = interaction.guild.id
        await interaction.response.edit_message(embed=self.build_embed(interaction.channel.id))

    @discord.ui.button(label="⬅️ 關閉面板", style=discord.ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction, button):
        await interaction.response.edit_message(content="面板已關閉。", embed=None, view=None)


class AlarmAddModal(discord.ui.Modal, title="⏰ 新增鬧鐘"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.time_input = discord.ui.TextInput(
            label="時間 (HH:MM)", placeholder="例如 16:30", max_length=5, required=True
        )
        self.reason_input = discord.ui.TextInput(
            label="原因 (可留空)", placeholder="例如 洗澡", max_length=50, required=False
        )
        self.add_item(self.time_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction):
        parsed = parse_time_str(self.time_input.value)
        if parsed is None:
            return await interaction.response.send_message("❌ 時間格式錯誤！請使用 `HH:MM`，例如 `16:30`。", ephemeral=True)
        reason = self.reason_input.value.strip() if self.reason_input.value else "起床"
        if not reason:
            reason = "起床"
        await interaction.response.send_message("選擇提醒頻率後點擊「✅ 設定完成」：",
                                                 view=AlarmFreqView(self.cog, parsed, reason, interaction.user.id),
                                                 ephemeral=True)


class AlarmFreqSelect(discord.ui.Select):
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


class AlarmFreqView(discord.ui.View):
    """選擇頻率 + 設定完成"""

    def __init__(self, cog, time_str, reason, user_id):
        super().__init__(timeout=120)
        self.cog = cog
        self.time_str = time_str
        self.reason = reason
        self.user_id = user_id
        self.selected = "daily"
        self.add_item(AlarmFreqSelect(self))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有設定的人可以操作！", ephemeral=True)
            return False
        return True

    async def update_embed(self, interaction):
        preset = PRESETS.get(self.selected, PRESETS["daily"])
        embed = discord.Embed(title="⏰ 設定鬧鐘", color=0x2ecc71)
        embed.add_field(name="🕐 時間", value=f"**{self.time_str}**", inline=True)
        embed.add_field(name="📝 原因", value=self.reason, inline=True)
        embed.add_field(name="🔁 頻率", value=preset["label"], inline=False)
        embed.set_footer(text="選擇頻率後點擊「✅ 設定完成」")
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="✅ 設定完成", style=discord.ButtonStyle.green)
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
                await interaction.response.send_message(f"❌ 本頻道已經有 `{self.time_str}` 的鬧鐘了！", ephemeral=True)
                return

        self.cog.alarms[gid][cid].append({
            "time": self.time_str, "reason": self.reason, "user_id": self.user_id,
            "last_fired": None, "schedule": schedule, "target_date": target_date,
        })
        self.cog._save_alarms()

        embed = discord.Embed(title="✅ 鬧鐘設定完成", color=0x2ecc71)
        embed.add_field(name="🕐 時間", value=f"**{self.time_str}**", inline=True)
        embed.add_field(name="📝 原因", value=self.reason, inline=True)
        embed.add_field(name="🔁 頻率", value=preset["label"], inline=False)
        embed.set_footer(text=f"到了 {self.time_str} 會提醒你 {MSGS} 次")
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class AlarmDeleteSelect(discord.ui.Select):
    def __init__(self, view):
        self.view = view
        options = []
        for i, a in enumerate(view.lst, 1):
            sched = a.get("schedule") or {}
            label = f"{a['time']} · {sched.get('label','每天')} · {a.get('reason','')[:20]}"
            options.append(discord.SelectOption(label=label[:50], value=str(i - 1)))
        super().__init__(placeholder="選擇要取消的鬧鐘...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction):
        self.view.index = int(self.values[0])
        alarm = self.view.lst[self.view.index]
        await interaction.response.edit_message(
            content=f"已選擇 `{alarm['time']}`，請按「🗑️ 確認取消」。"
        )


class AlarmDeleteView(discord.ui.View):
    """取消鬧鐘"""

    def __init__(self, cog, guild_id, channel):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id
        self.channel = channel
        gid = str(guild_id)
        self.lst = cog.alarms.get(gid, {}).get(str(channel.id), [])
        self.index = None
        self.add_item(AlarmDeleteSelect(self))

    @discord.ui.button(label="🗑️ 確認取消", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        if self.index is None:
            return await interaction.response.send_message("請先從選單選擇要取消的鬧鐘！", ephemeral=True)
        gid = str(self.guild_id)
        cid = str(self.channel.id)
        current_list = self.cog.alarms.get(gid, {}).get(cid, [])
        if self.index >= len(current_list):
            return await interaction.response.send_message("❌ 這個鬧鐘已不存在，請重新開啟鬧鐘面板。", ephemeral=True)
        alarm = current_list[self.index]
        if alarm.get("user_id") != interaction.user.id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 只有設定的人或管理員可以取消！", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        del current_list[self.index]
        self.cog._save_alarms()
        await interaction.edit_original_response(content=f"✅ 已取消 `{alarm['time']}` 的鬧鐘！", embed=None, view=None)


class AlarmCog(commands.Cog):
    """鬧鐘系統 - 定時提醒"""

    def __init__(self, bot):
        self.bot = bot
        self.alarms = self._load_alarms()
        self._current_guild_id = 0
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
        sched = alarm.get("schedule") or {"type": "daily"}
        stype = sched.get("type", "daily")
        if stype == "today":
            return alarm.get("target_date") == today_str
        if stype == "weekdays":
            return today_weekday in sched.get("days", [])
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


    @commands.command(name="鬧鐘", aliases=["alarm"])
    async def alarm_panel(self, ctx):
        """開啟鬧鐘面板，可新增或取消鬧鐘"""
        self._current_guild_id = ctx.guild.id if ctx.guild else 0
        view = AlarmPanelView(self)
        embed = view.build_embed(ctx.channel.id)
        view.message = await ctx.send(embed=embed, view=view)

    @commands.command(name="鬧鐘快捷")
    async def alarm_quick(self, ctx, time_str: str = None, *, reason: str = None):
        """快速設定鬧鐘 - 例如: !鬧鐘快捷 16:30 洗澡"""
        if time_str is None:
            return await ctx.send("❓ 用法：`!鬧鐘快捷 16:30 洗澡`")
        parsed = parse_time_str(time_str)
        if parsed is None:
            return await ctx.send("❌ 時間格式錯誤，請用 `HH:MM`。")
        if not reason:
            reason = "起床"
        # 直接進入頻率選單
        embed = discord.Embed(title="⏰ 設定鬧鐘", color=0x2ecc71)
        embed.add_field(name="🕐 時間", value=f"**{parsed}**", inline=True)
        embed.add_field(name="📝 原因", value=reason, inline=True)
        embed.set_footer(text="選擇頻率後點擊「✅ 設定完成」")
        await ctx.send(embed=embed, view=AlarmFreqView(self, parsed, reason, ctx.author.id))


async def setup(bot):
    await bot.add_cog(AlarmCog(bot))
