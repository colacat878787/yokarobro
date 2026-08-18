import discord
from discord.ext import commands
import json
import os
from datetime import datetime

# 可切換的功能模組（排除核心系統模組）
TOGGLEABLE_COGS = {
    "AICog": "🧠 AI 對話系統",
    "MusicCog": "🎵 音樂播放系統",
    "VoiceAICog": "🎤 語音 AI 系統",
    "LevelsCog": "📊 等級系統",
    "InfoCog": "🔍 實用工具",
    "FunCog": "🎮 趣味指令",
    "TwitterCog": "🐦 Twitter 整合",
    "TTSCog": "🔊 文字轉語音",
    "WelcomeCog": "👋 歡迎系統",
    "RecordCog": "🎥 錄影系統",
    "EconomyCog": "💰 經濟系統",
    "KujiCog": "🎟️ 一番賞系統",
    "ModmailCog": "📩 客服信箱",
    "TicketsCog": "🎫 票單系統",
    "MusicRecommendCog": "🎶 音樂推薦",
    "OtakuCog": "🥰 御宅文化",
    "GamesCog": "🎲 遊戲系統",
    "WerewolfCog": "🐺 狼人殺",
    "WidgetCog": "📊 伺服器小工具",
    "MCStatusCog": "⛏️ Minecraft 狀態",
    "GreetingButtonsCog": "🤝 打招呼按鈕",
    "CheckinCardsCog": "📅 每日簽到+抽卡",
    "ConfessionCog": "💌 匿名告白牆",
    "StocksCog": "📈 股票市場",
    "AlienCog": "👽 外星文翻譯",
    "ProfanityCog": "🚫 髒話過濾",
    "BackupCog": "💾 伺服器備份",
    "ScreenshotCog": "📸 網頁截圖",
    "ReactionCog": "😀 表情符號反應",
    "OAuthCog": "🔐 OAuth 加入伺服器",
    "CasinoCog": "🎰 賭場系統",
    "PetsCog": "🐾 寵物系統",
    "FinanceCog": "💳 財務系統",
}

# 不可切換的核心模組
CORE_COGS = {
    "SecurityCog", "WebPanelCog", "ManagementCog", "SystemCog",
    "MusicWebPanelCog", "UpdaterCog", "ReloaderCog", "DeleteLogCog",
    "TestSystemCog", "AdminCog", "ServerSettingsCog"
}

SETTINGS_FILE = "server_settings.json"

class ServerSettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = self._load_settings()
        
        # 註冊全域指令檢查
        self.bot.add_check(self._check_cog_enabled)
    
    def _load_settings(self):
        """載入伺服器設定"""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_settings(self):
        """儲存伺服器設定"""
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)
    
    def is_cog_enabled(self, guild_id: int, cog_name: str) -> bool:
        """檢查某個 cog 在某個伺服器是否啟用"""
        guild_str = str(guild_id)
        if guild_str not in self.settings:
            return True  # 預設啟用
        disabled = self.settings[guild_str].get("disabled_cogs", [])
        return cog_name not in disabled
    
    def _check_cog_enabled(self, ctx):
        """全域指令檢查 - 攔截所有指令"""
        # 只在伺服器中檢查
        if not ctx.guild:
            return True
        
        # 取得指令所屬的 cog 名稱
        if ctx.command and ctx.command.cog:
            cog_name = ctx.command.cog.__class__.__name__
            
            # 核心模組不受限制
            if cog_name in CORE_COGS:
                return True
            
            # 檢查是否被停用
            if not self.is_cog_enabled(ctx.guild.id, cog_name):
                raise commands.DisabledCommand()
        
        return True
    
    @commands.command(name='用戶面板', aliases=['面板', 'settings', 'serversettings'])
    @commands.has_permissions(administrator=True)
    async def server_panel_command(self, ctx):
        """顯示伺服器功能開關面板"""
        guild_id = str(ctx.guild.id)
        
        # 確保設定存在
        if guild_id not in self.settings:
            self.settings[guild_id] = {"disabled_cogs": []}
            self._save_settings()
        
        disabled_cogs = self.settings[guild_id].get("disabled_cogs", [])
        
        # 建立嵌入訊息
        embed = discord.Embed(
            title="⚙️ 伺服器功能面板",
            description="從下方選單選擇要開啟或關閉的功能模組。\n"
                        "關閉的功能將無法在這個伺服器使用。",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        
        # 顯示目前狀態
        enabled_lines, disabled_lines, unloaded_lines = self._build_cog_status_lines(ctx.guild.id)
        
        # 分組顯示狀態
        embed.add_field(
            name=f"✅ 已啟用 ({len(enabled_lines)})",
            value="\n".join(enabled_lines) or "無",
            inline=True
        )
        embed.add_field(
            name=f"❌ 已停用 ({len(disabled_lines)})",
            value="\n".join(disabled_lines) or "無",
            inline=True
        )
        if unloaded_lines:
            embed.add_field(
                name=f"⚪ 未載入 ({len(unloaded_lines)})",
                value="\n".join(unloaded_lines),
                inline=False
            )
        
        embed.set_footer(text="只有伺服器管理員可以操作此面板")
        
        # 建立下拉選單
        view = CogToggleView(self, ctx.guild.id)
        
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name='功能列表', aliases=['coglist'])
    async def show_server_cog_status(self, ctx):
        """顯示所有功能模組的狀態"""
        if not ctx.guild:
            return await ctx.send("❌ 此指令只能在伺服器中使用")
        
        guild_id = str(ctx.guild.id)
        disabled_cogs = self.settings.get(guild_id, {}).get("disabled_cogs", [])
        
        embed = discord.Embed(
            title="📋 功能模組列表",
            description=f"以下是所有可切換的功能模組：",
            color=0x3498db,
            timestamp=datetime.now()
        )
        
        enabled_list, disabled_list, unloaded_list = self._build_cog_status_lines(ctx.guild.id)
        
        embed.add_field(
            name=f"✅ 已啟用 ({len(enabled_list)})",
            value="\n".join(enabled_list) if enabled_list else "無",
            inline=False
        )
        
        if disabled_list:
            embed.add_field(
                name=f"❌ 已停用 ({len(disabled_list)})",
                value="\n".join(disabled_list) if disabled_list else "無",
                inline=False
            )

        if unloaded_list:
            embed.add_field(
                name=f"⚪ 未載入 ({len(unloaded_list)})",
                value="\n".join(unloaded_list) if unloaded_list else "無",
                inline=False
            )
        
        embed.set_footer(text="使用 !用戶面板 來切換功能")
        
        await ctx.send(embed=embed)
    
    def _build_cog_status_lines(self, guild_id: int):
        """建立顯示用的功能狀態清單，包含未載入的模組，讓面板能明確看到所有可切換項目。"""
        guild_str = str(guild_id)
        disabled_cogs = self.settings.get(guild_str, {}).get("disabled_cogs", [])

        enabled_lines = []
        disabled_lines = []
        unloaded_lines = []

        for cog_name, display_name in TOGGLEABLE_COGS.items():
            cog = self.bot.get_cog(cog_name)
            if cog is None:
                unloaded_lines.append(f"⚪ {display_name}（未載入）")
                continue

            if cog_name in disabled_cogs:
                disabled_lines.append(f"🔴 {display_name}")
            else:
                enabled_lines.append(f"🟢 {display_name}")

        return enabled_lines, disabled_lines, unloaded_lines

    def toggle_cog(self, guild_id: int, cog_name: str) -> bool:
        """切換 cog 的啟用/停用狀態，返回新的狀態 (True=啟用, False=停用)"""
        guild_str = str(guild_id)
        
        if guild_str not in self.settings:
            self.settings[guild_str] = {"disabled_cogs": []}
        
        disabled = self.settings[guild_str].get("disabled_cogs", [])
        
        if cog_name in disabled:
            # 目前停用，切換為啟用
            disabled.remove(cog_name)
            self.settings[guild_str]["disabled_cogs"] = disabled
            self._save_settings()
            return True
        else:
            # 目前啟用，切換為停用
            disabled.append(cog_name)
            self.settings[guild_str]["disabled_cogs"] = disabled
            self._save_settings()
            return False


class CogToggleView(discord.ui.View):
    """功能開關下拉選單"""
    
    def __init__(self, settings_cog: ServerSettingsCog, guild_id: int):
        super().__init__(timeout=300)
        self.settings_cog = settings_cog
        self.guild_id = guild_id
        
        # 建立下拉選單選項
        options = []
        disabled_cogs = settings_cog.settings.get(str(guild_id), {}).get("disabled_cogs", [])
        
        for cog_name, display_name in TOGGLEABLE_COGS.items():
            cog = settings_cog.bot.get_cog(cog_name)
            is_loaded = cog is not None
            is_disabled = cog_name in disabled_cogs

            if is_loaded:
                description = "🔴 已停用" if is_disabled else "🟢 已啟用"
                emoji = "🔴" if is_disabled else "🟢"
            else:
                description = "⚪ 未載入"
                emoji = "⚪"
            
            options.append(discord.SelectOption(
                label=display_name[:100],
                description=description,
                value=cog_name,
                emoji=emoji
            ))
        
        # Discord 單一下拉選單最多 25 個選項，改為分批建立多個選單
        option_chunks = [options[i:i+25] for i in range(0, len(options), 25)]

        for index, chunk in enumerate(option_chunks, start=1):
            select = discord.ui.Select(
                placeholder=f"選擇要切換的功能模組... ({index}/{len(option_chunks)})",
                min_values=1,
                max_values=min(len(chunk), 25),
                options=chunk,
                custom_id=f"cog_toggle_select_{index}"
            )
            
            select.callback = self.select_callback
            self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        """處理下拉選單選擇"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 只有管理員可以操作此面板", ephemeral=True)
        
        selected_cogs = interaction.data["values"]
        results = []
        
        for cog_name in selected_cogs:
            new_state = self.settings_cog.toggle_cog(self.guild_id, cog_name)
            display_name = TOGGLEABLE_COGS.get(cog_name, cog_name)
            status = "🟢 已啟用" if new_state else "🔴 已停用"
            results.append(f"{display_name} → {status}")
        
        # 更新嵌入訊息
        guild_id_str = str(self.guild_id)
        disabled_cogs = self.settings_cog.settings.get(guild_id_str, {}).get("disabled_cogs", [])
        
        enabled_lines, disabled_lines, unloaded_lines = self.settings_cog._build_cog_status_lines(self.guild_id)
        
        embed = discord.Embed(
            title="⚙️ 伺服器功能面板",
            description="✅ 已更新功能設定！\n\n" + "\n".join(results),
            color=0x2ed573,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name=f"✅ 已啟用 ({len(enabled_lines)})",
            value="\n".join(enabled_lines) or "無",
            inline=True
        )
        embed.add_field(
            name=f"❌ 已停用 ({len(disabled_lines)})",
            value="\n".join(disabled_lines) or "無",
            inline=True
        )
        if unloaded_lines:
            embed.add_field(
                name=f"⚪ 未載入 ({len(unloaded_lines)})",
                value="\n".join(unloaded_lines),
                inline=False
            )
        
        embed.set_footer(text="只有伺服器管理員可以操作此面板")
        
        # 更新下拉選單
        view = CogToggleView(self.settings_cog, self.guild_id)
        
        await interaction.response.edit_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(ServerSettingsCog(bot))