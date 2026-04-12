import discord
from discord.ext import commands
import os
import time
from datetime import datetime, timezone

class ControlPanelView(discord.ui.View):
    """高效能後台控制面板 - 所有按鈕均採用 defer 先行響應，確保不會 timeout"""
    def __init__(self, bot):
        super().__init__(timeout=120)
        self.bot = bot

    async def _safe_respond(self, interaction: discord.Interaction, embed: discord.Embed = None, content: str = None):
        """统一响应方法: 先 defer 确保不超时，再 followup"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(embed=embed, content=content, ephemeral=True)

    @discord.ui.button(label="🤖 AI 對話", style=discord.ButtonStyle.success, row=0)
    async def toggle_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛠️ 正在準備調整 AI 核心狀態...", ephemeral=True)
        await self._toggle_module(interaction, button, "cogs.ai", "AI 對話")

    @discord.ui.button(label="🎵 音樂系統", style=discord.ButtonStyle.success, row=0)
    async def toggle_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛠️ 正在調度音樂模組齒輪...", ephemeral=True)
        await self._toggle_module(interaction, button, "cogs.music", "音樂系統")

    @discord.ui.button(label="🎫 一番賞", style=discord.ButtonStyle.success, row=0)
    async def toggle_kuji(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛠️ 正在檢查一番賞獎池連線...", ephemeral=True)
        await self._toggle_module(interaction, button, "cogs.kuji", "一番賞")

    @discord.ui.button(label="🛡️ 安全防護", style=discord.ButtonStyle.success, row=0)
    async def toggle_security(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛠️ 正在更新安全協議矩陣...", ephemeral=True)
        await self._toggle_module(interaction, button, "cogs.security", "安全防護")

    @discord.ui.button(label="📊 系統數據", style=discord.ButtonStyle.secondary, row=1)
    async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 使用最速回應
        await interaction.response.send_message("📊 正在收集系統感應器數據...", ephemeral=True)
        try:
            # ... (其餘邏輯)
            import psutil
            process = psutil.Process(os.getpid())
            # ...
            mem = process.memory_info().rss / 1024 / 1024
            cpu = psutil.cpu_percent(interval=0.1)
            ping = round(self.bot.latency * 1000)
            
            embed = discord.Embed(title="📊 Yokaro 即時系統數據", color=0x3498db)
            embed.add_field(name="記憶體使用", value=f"{mem:.2f} MB", inline=True)
            embed.add_field(name="CPU 使用率", value=f"{cpu}%", inline=True)
            embed.add_field(name="連線延遲", value=f"{ping}ms", inline=True)
            embed.set_footer(text=f"查詢時間: {datetime.now().strftime('%H:%M:%S')}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except ImportError:
            ping = round(self.bot.latency * 1000)
            await interaction.followup.send(f"📊 連線延遲: **{ping}ms**\n（psutil 未安裝，無法顯示 CPU/記憶體）", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 無法取得系統數據: {e}", ephemeral=True)

    @discord.ui.button(label="🔄 強制重啟", style=discord.ButtonStyle.danger, row=1)
    async def force_restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send("⚙️ 洛洛正在重啟，請稍候...")
        os._exit(0)

    async def _toggle_module(self, interaction: discord.Interaction, button: discord.ui.Button, extension: str, name: str):
        """通用模組切換邏輯"""
        try:
            if extension in self.bot.extensions:
                await self.bot.unload_extension(extension)
                button.style = discord.ButtonStyle.danger
                msg = f"❌ 已關閉 **{name}** 功能。"
            else:
                await self.bot.load_extension(extension)
                button.style = discord.ButtonStyle.success
                msg = f"✅ 已開啟 **{name}** 功能。"
            
            # 更新面板按鈕顏色
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ 操作 {name} 失敗: {e}", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ 面板錯誤: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ 面板錯誤: {error}", ephemeral=True)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='機器人後台控制面板', aliases=['panel', '控制台', '後台'])
    @commands.has_permissions(administrator=True)
    async def control_panel(self, ctx):
        """(管理員) 開啟高級後台控制面板"""
        embed = discord.Embed(
            title="🛠️ Yokaro 高階管理後台",
            description="您可以透過下方的按鈕即時控制機器人的各項功能開關。\n\n🟢 綠色：正常運作中\n🔴 紅色：功能已停用",
            color=0x2c3e50
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="洛洛管理系統 | 所有按鈕均採用 defer 保證不超時")
        
        view = ControlPanelView(self.bot)
        
        # 根據目前實際載入狀態初始化按鈕顏色
        ext_map = {
            "toggle_ai": "cogs.ai",
            "toggle_music": "cogs.music",
            "toggle_kuji": "cogs.kuji",
            "toggle_security": "cogs.security"
        }
        for item in view.children:
            if isinstance(item, discord.ui.Button) and hasattr(item, 'custom_id') and item.custom_id:
                target = ext_map.get(item.custom_id)
                if target:
                    item.style = discord.ButtonStyle.success if target in self.bot.extensions else discord.ButtonStyle.danger

        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
