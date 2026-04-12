import discord
from discord.ext import commands
import os
import psutil
import time

class ControlPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🤖 AI 對話", style=discord.ButtonStyle.success, custom_id="toggle_ai")
    async def toggle_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_cog(interaction, button, "cogs.ai", "🤖 AI 對話")

    @discord.ui.button(label="🎵 音樂系統", style=discord.ButtonStyle.success, custom_id="toggle_music")
    async def toggle_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_cog(interaction, button, "cogs.music", "🎵 音樂系統")

    @discord.ui.button(label="🎫 一番賞", style=discord.ButtonStyle.success, custom_id="toggle_kuji")
    async def toggle_kuji(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_cog(interaction, button, "cogs.kuji", "🎫 一番賞")

    @discord.ui.button(label="🛡️ 安全防護", style=discord.ButtonStyle.success, custom_id="toggle_security")
    async def toggle_security(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_cog(interaction, button, "cogs.security", "🛡️ 安全防護")

    @discord.ui.button(label="📊 系統數據", style=discord.ButtonStyle.secondary, custom_id="stats")
    async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        process = psutil.Process(os.getpid())
        mem = process.memory_info().rss / 1024 / 1024
        cpu = psutil.cpu_percent()
        ping = round(self.bot.latency * 1000)
        
        embed = discord.Embed(title="📊 Yokaro 即時系統數據", color=0x3498db)
        embed.add_field(name="記憶體使用", value=f"{mem:.2f} MB", inline=True)
        embed.add_field(name="CPU 使用率", value=f"{cpu}%", inline=True)
        embed.add_field(name="連線延遲", value=f"{ping}ms", inline=True)
        embed.set_footer(text=f"最後更新時間: {datetime.now().strftime('%H:%M:%S')}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def toggle_cog(self, interaction, button, extension, name):
        # 0.1s 反應優化: 立即處理邏輯並更新按鈕狀態
        try:
            if extension in self.bot.extensions:
                await self.bot.unload_extension(extension)
                button.style = discord.ButtonStyle.danger
                msg = f"❌ 已關閉 {name} 功能。"
            else:
                await self.bot.load_extension(extension)
                button.style = discord.ButtonStyle.success
                msg = f"✅ 已開啟 {name} 功能。"
            
            # 使用 edit_message 達成極速視覺更新
            await interaction.response.edit_message(view=self)
            # 額外發送一個短訊提醒 (ephemeral)
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 操作失敗: {e}", ephemeral=True)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='機器人後台控制面板', aliases=['panel', '控制台'])
    @commands.has_permissions(administrator=True)
    async def control_panel(self, ctx):
        """(管理員) 開啟高級後台控制面板"""
        embed = discord.Embed(
            title="🛠️ Yokaro 高階管理後台",
            description="您可以透過下方的按鈕即時控制機器人的各項功能開關。\n\n🟢 綠色：正常運作中\n🔴 紅色：功能已停用",
            color=0x2c3e50
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="洛洛管理系統 | 極致效能 0.1s 回應模式")
        
        view = ControlPanelView(self.bot)
        
        # 初始化按鈕外觀
        for item in view.children:
            if isinstance(item, discord.ui.Button) and item.custom_id:
                ext_map = {
                    "toggle_ai": "cogs.ai",
                    "toggle_music": "cogs.music",
                    "toggle_kuji": "cogs.kuji",
                    "toggle_security": "cogs.security"
                }
                target_ext = ext_map.get(item.custom_id)
                if target_ext:
                    item.style = discord.ButtonStyle.success if target_ext in self.bot.extensions else discord.ButtonStyle.danger

        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
