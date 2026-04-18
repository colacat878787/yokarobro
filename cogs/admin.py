import discord
from discord.ext import commands
import os
import psutil
from utils.config import config_manager

# --- Modals ---

class StringConfigModal(discord.ui.Modal):
    def __init__(self, title, key, current_val):
        super().__init__(title=title)
        self.key = key
        self.input = discord.ui.TextInput(
            label=f"修改 {key}",
            placeholder="請輸入新數值...",
            default=str(current_val) if current_val else "",
            required=True
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        config_manager.set_guild_setting(interaction.guild.id, self.key, self.input.value)
        await interaction.response.send_message(f"✅ 已成功將 `{self.key}` 修改為：`{self.input.value}`", ephemeral=True)

# --- Sub-Menus ---

class ModuleSettingsView(discord.ui.View):
    def __init__(self, bot, parent_view):
        super().__init__(timeout=60)
        self.bot = bot
        self.parent_view = parent_view
        self._update_buttons()

    def _update_buttons(self):
        # 這裡動態判定模組狀態
        exts = {
            "cogs.ai": "AI 對話",
            "cogs.music": "音樂系統",
            "cogs.kuji": "一番賞系統",
            "cogs.security": "安全防護",
            "cogs.record": "錄影系統",
            "cogs.economy": "經濟系統"
        }
        self.clear_items()
        for path, name in exts.items():
            is_on = path in self.bot.extensions
            style = discord.ButtonStyle.success if is_on else discord.ButtonStyle.danger
            btn = discord.ui.Button(label=name, style=style, custom_id=f"toggle_{path}")
            btn.callback = self._create_callback(path, name)
            self.add_item(btn)
        
        # 回到主選單按鈕
        back_btn = discord.ui.Button(label="⬅️ 返回主選單", style=discord.ButtonStyle.secondary, row=4)
        back_btn.callback = self._back_to_main
        self.add_item(back_btn)

    def _create_callback(self, path, name):
        async def callback(interaction: discord.Interaction):
            try:
                if path in self.bot.extensions:
                    await self.bot.unload_extension(path)
                    msg = f"❌ 已關閉 {name}"
                else:
                    await self.bot.load_extension(path)
                    msg = f"✅ 已開啟 {name}"
                self._update_buttons()
                await interaction.response.edit_message(view=self)
                await interaction.followup.send(msg, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"⚠️ 操作失敗: {e}", ephemeral=True)
        return callback

    async def _back_to_main(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="🔧 請選擇你要修改的設定類別：", view=self.parent_view)

class ConfigSettingsView(discord.ui.View):
    def __init__(self, bot, parent_view, category):
        super().__init__(timeout=60)
        self.bot = bot
        self.parent_view = parent_view
        self.category = category
        self._setup_buttons()

    def _setup_buttons(self):
        # 根據類別顯示不同的設定按鈕
        self.clear_items()
        configs = []
        if self.category == "security":
            configs = [("驗證身分組名稱", "verify_role"), ("工作人員身分組", "staff_role")]
        elif self.category == "features":
            configs = [("XP 獲取倍率", "xp_rate")]
        
        # 重新設計按鈕加載邏輯以支援切換按鈕
        if self.category == "modmail":
            self._add_modmail_buttons()
        else:
            for label, key in configs:
                btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
                btn.callback = self._create_modal_callback(label, key)
                self.add_item(btn)

        back_btn = discord.ui.Button(label="⬅️ 返回主選單", style=discord.ButtonStyle.secondary, row=4)
        back_btn.callback = self._back_to_main
        self.add_item(back_btn)

    def _add_modmail_buttons(self):
        # 因為 View 需要知道 guild_id，我們稍後在 callback 中獲取
        btn_anon = discord.ui.Button(label="👤 切換匿名/實名模式", style=discord.ButtonStyle.primary)
        async def toggle_anon_callback(interaction: discord.Interaction):
            settings = config_manager.get_guild_settings(interaction.guild.id)
            current = settings.get("modmail_anonymous", True)
            config_manager.set_guild_setting(interaction.guild.id, "modmail_anonymous", not current)
            mode = "匿名" if not current else "實名 (顯示名字)"
            await interaction.response.send_message(f"✅ Modmail 模式已切換為：**{mode}**", ephemeral=True)
            
        btn_anon.callback = toggle_anon_callback
        self.add_item(btn_anon)

    def _create_modal_callback(self, label, key):
        async def callback(interaction: discord.Interaction):
            settings = config_manager.get_guild_settings(interaction.guild_id)
            await interaction.response.send_modal(StringConfigModal(label, key, settings.get(key)))
        return callback

    async def _back_to_main(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="🔧 請選擇你要修改的設定類別：", view=self.parent_view)

# --- Main Admin Panel ---

class ControlPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🔧 模組開關", style=discord.ButtonStyle.primary, row=0)
    async def modules(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ModuleSettingsView(self.bot, self)
        await interaction.response.edit_message(content="📂 **[模組設定]** 點擊下方按鈕切換功能開關：", view=view)

    @discord.ui.button(label="🔰 安全與身分組", style=discord.ButtonStyle.primary, row=0)
    async def security_cfg(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfigSettingsView(self.bot, self, "security")
        await interaction.response.edit_message(content="🛡️ **[安全設定]** 修改驗證與權限相關參數：", view=view)

    @discord.ui.button(label="📩 聯絡/支援設定", style=discord.ButtonStyle.primary, row=0)
    async def modmail_cfg(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfigSettingsView(self.bot, self, "modmail")
        await interaction.response.edit_message(content="📩 **[聯絡設定]** 設定 Modmail 的匿名性與運作方式：", view=view)

    @discord.ui.button(label="📊 系統數據", style=discord.ButtonStyle.secondary, row=1)
    async def stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        process = psutil.Process(os.getpid())
        mem = process.memory_info().rss / 1024 / 1024
        cpu = psutil.cpu_percent(interval=0.1)
        
        embed = discord.Embed(title="📊 Yokaro 實時監測", color=0x3498db)
        embed.add_field(name="🌡️ CPU", value=f"{cpu}%", inline=True)
        embed.add_field(name="🧠 RAM", value=f"{mem:.1f} MB", inline=True)
        embed.add_field(name="🛰️ 延遲", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔄 重啟機器人", style=discord.ButtonStyle.danger, row=1)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ 正在執行熱重啟...")
        os._exit(0)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(ControlPanelView(bot))

    @commands.command(name='panel', aliases=['後台', '控制台'])
    @commands.has_permissions(administrator=True)
    async def control_panel(self, ctx):
        embed = discord.Embed(
            title="🛠️ Yokaro 高階管理後台 V2",
            description="歡迎來到全功能管理面板！請點擊下方按鈕進行細項設定。",
            color=0x2c3e50
        )
        embed.set_footer(text="提示：所有修改將即時儲存至 guild_settings.json")
        await ctx.send(embed=embed, view=ControlPanelView(self.bot))

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
