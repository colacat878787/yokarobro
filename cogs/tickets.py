import discord
from discord.ext import commands
import asyncio
from utils.config import config_manager

class TicketCloseView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="🔒 關閉票單", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 僅限管理員或發案人 (這裡設定為管理員權限者)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 只有管理員可以關閉票單喔！", ephemeral=True)
        
        await interaction.response.send_message("⚠️ 確定要關閉自銷毀此頻道嗎？", view=TicketDestroyConfirmView(self.cog), ephemeral=False)

class TicketDestroyConfirmView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog

    @discord.ui.button(label="✅ 確定銷毀", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🧨 頻道將在 5 秒後銷毀...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="✅ 已取消銷毀，頻道將保留。", view=None)

class TicketDashboardView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="🎫 開啟票單 (Open Ticket)", style=discord.ButtonStyle.primary, custom_id="open_ticket_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.cog.create_ticket(interaction)

class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TicketDashboardView(self))
        self.bot.add_view(TicketCloseView(self))

    async def get_or_create_category(self, guild):
        category_name = "🎫 | 支援票單 (Tickets)"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
            }
            category = await guild.create_category(category_name, overwrites=overwrites)
        return category

    async def create_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = await self.get_or_create_category(guild)
        
        # 建立私密頻道
        channel_name = f"ticket-{interaction.user.name}".replace(" ", "-").lower()
        
        # 權限：只有用戶自己跟管理員看得到
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        # 找出管理員身分組 (這裡簡化為管理員權限者，之後可以在 Panel 設定特定身分組)
        # 我們讓 Administrator 權限的人預設能看到所有頻道，所以不需要額外 overwrite
        
        try:
            channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
            
            embed = discord.Embed(title="🎫 票單已開啟", description=f"哈囉 {interaction.user.mention}！\n請描述你遇到的問題，管理團隊會盡快為您處理。嗷嗷嗷～", color=0x2ecc71)
            embed.set_footer(text="處理完畢後，管理員可點擊下方按鈕結案")
            
            await channel.send(embed=embed, view=TicketCloseView(self))
            await interaction.followup.send(f"✅ 票單已建立：{channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 建立票單失敗: {e}", ephemeral=True)

    @commands.command(name='ticket', aliases=['開單', '票單'])
    @commands.has_permissions(administrator=True)
    async def ticket_dashboard(self, ctx):
        """(管理員) 發送票單啟動儀表板"""
        embed = discord.Embed(
            title="🎫 官方支援中心",
            description="如果您有任何問題、檢舉、或是需要管理員協助的事項，請點擊下方按鈕開啟專屬票單。\n\n⚠️ **請勿濫用此系統，謝謝配合！**",
            color=0x3498db
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="洛洛支援系統 | 優質服務 嗷嗷嗷～")
        
        await ctx.send(embed=embed, view=TicketDashboardView(self))

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))
