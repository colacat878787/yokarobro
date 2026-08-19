"""個人問候與使用者設定。"""

import json
import os
from datetime import datetime

import discord
from discord.ext import commands


USER_SETTINGS_FILE = "user_settings.json"
DEFAULT_MESSAGES = {
    "morning": "早安，{name}！新的一天開始了，記得吃早餐喔。",
    "lunch": "{name}，今天已經過一半了，記得吃午餐！",
    "evening": "{name}，今天工作辛苦了，晚上好好休息喔。",
}
PERIOD_LABELS = {
    "morning": "早安（01:00-10:59）",
    "lunch": "午餐（11:00-16:59）",
    "evening": "晚上（17:00-00:59）",
}


class UserGreetingModal(discord.ui.Modal):
    def __init__(self, cog, user_id, period):
        super().__init__(title=f"修改{PERIOD_LABELS[period]}訊息")
        self.cog = cog
        self.user_id = str(user_id)
        self.period = period
        current = cog.get_settings(user_id)["messages"][period]
        self.message = discord.ui.TextInput(
            label="問候內容",
            default=current[:4000],
            max_length=4000,
            required=True,
            placeholder="可使用 {name} 代入你的顯示名稱",
        )
        self.add_item(self.message)

    async def on_submit(self, interaction: discord.Interaction):
        settings = self.cog.get_settings(int(self.user_id))
        settings["messages"][self.period] = self.message.value.strip()
        self.cog.save_settings()
        await interaction.response.send_message(
            f"✅ 已更新「{PERIOD_LABELS[self.period]}」問候內容。", ephemeral=True
        )


class UserSettingsView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        settings = cog.get_settings(user_id)
        self.enabled_button = discord.ui.Button(
            label="關閉每日問候" if settings["enabled"] else "開啟每日問候",
            style=discord.ButtonStyle.danger if settings["enabled"] else discord.ButtonStyle.success,
            row=0,
        )
        self.enabled_button.callback = self.toggle_enabled
        self.add_item(self.enabled_button)
        for period, label in PERIOD_LABELS.items():
            button = discord.ui.Button(label=f"修改{label.split('（')[0]}訊息", style=discord.ButtonStyle.secondary)
            button.callback = self.make_edit_callback(period)
            self.add_item(button)

    async def toggle_enabled(self, interaction: discord.Interaction):
        settings = self.cog.get_settings(self.user_id)
        settings["enabled"] = not settings["enabled"]
        self.cog.save_settings()
        state = "開啟" if settings["enabled"] else "關閉"
        await interaction.response.edit_message(
            content=f"⚙️ 個人問候已{state}。再次點擊可切換。",
            view=UserSettingsView(self.cog, self.user_id),
        )

    def make_edit_callback(self, period):
        async def callback(interaction: discord.Interaction):
            await interaction.response.send_modal(
                UserGreetingModal(self.cog, self.user_id, period)
            )
        return callback


class UserSettingsCog(commands.Cog):
    """使用者個人問候設定與時段問候。"""

    def __init__(self, bot):
        self.bot = bot
        self.settings = self._load_settings()

    def _load_settings(self):
        if os.path.exists(USER_SETTINGS_FILE):
            try:
                with open(USER_SETTINGS_FILE, "r", encoding="utf-8") as file:
                    return json.load(file)
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def save_settings(self):
        with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as file:
            json.dump(self.settings, file, ensure_ascii=False, indent=2)

    def get_settings(self, user_id):
        user_key = str(user_id)
        settings = self.settings.setdefault(
            user_key,
            {"enabled": True, "messages": dict(DEFAULT_MESSAGES), "last_greetings": {}},
        )
        settings.setdefault("enabled", True)
        settings.setdefault("messages", {})
        settings.setdefault("last_greetings", {})
        for period, message in DEFAULT_MESSAGES.items():
            settings["messages"].setdefault(period, message)
        return settings

    def current_period(self, hour):
        if 1 <= hour < 11:
            return "morning"
        if 11 <= hour < 17:
            return "lunch"
        return "evening"

    @commands.command(
        name="使用者設定",
        aliases=["使用者面板", "個人設定", "個人面板", "usersettings", "userpanel"],
    )
    async def user_settings(self, ctx):
        """開啟自己的每日問候設定面板。"""
        if not ctx.guild:
            await ctx.send("❌ 這個設定只能在伺服器頻道使用。")
            return
        self.get_settings(ctx.author.id)
        await ctx.send(
            "⚙️ 個人問候設定：可開關每日問候，或修改三個時段的訊息。",
            view=UserSettingsView(self, ctx.author.id),
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        now = datetime.now()
        period = self.current_period(now.hour)
        today = now.strftime("%Y-%m-%d")
        settings = self.get_settings(message.author.id)
        if not settings["enabled"] or settings["last_greetings"].get(period) == today:
            return

        settings["last_greetings"][period] = today
        self.save_settings()
        template = settings["messages"].get(period, DEFAULT_MESSAGES[period])
        try:
            greeting = template.replace("{name}", message.author.display_name)
            await message.channel.send(greeting)
        except (discord.Forbidden, discord.HTTPException):
            settings["last_greetings"].pop(period, None)
            self.save_settings()


async def setup(bot):
    await bot.add_cog(UserSettingsCog(bot))
