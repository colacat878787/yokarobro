import discord
from discord.ext import commands
from discord import app_commands
import random

class ContextMenusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # 鼓掌的鼓勵語
        self.cheer_messages = [
            "要繼續加油哦!!",
            "做得太好了！",
            "太厲害了！",
            "繼續保持哦！",
            "你是最棒的！",
            "不可思議的表現！",
            "令人欽佩！",
            "太優秀了！"
        ]
    
    # ===== 移植功能 =====
    @app_commands.context_menu(name="移植")
    async def transplant_context_menu(self, interaction: discord.Interaction, message: discord.Message):
        """將訊息內容複製到當前頻道（移植功能）"""
        # 檢查權限
        if not interaction.user.guild_permissions.manage_messages and str(interaction.user.id) != "1113353915010920452":
            await interaction.response.send_message("❌ 你沒有權限使用這個功能！", ephemeral=True)
            return
        
        # 檢查訊息內容
        if not message.content and not message.embeds:
            await interaction.response.send_message("❌ 這條訊息沒有內容可以移植！", ephemeral=True)
            return
        
        # 創建 embed 顯示原文
        embed = discord.Embed(
            title="📋 訊息移植",
            description=message.content or "*（此訊息只有附件或 embed）*",
            color=0x3498db,
            timestamp=message.created_at
        )
        
        # 添加作者資訊
        embed.set_author(
            name=f"{message.author.display_name} ({message.author})",
            icon_url=message.author.display_avatar.url
        )
        
        # 添加原始連結
        embed.add_field(
            name="🔗 原始訊息",
            value=f"[點擊查看]({message.jump_url})",
            inline=False
        )
        
        # 如果有 embed，添加說明
        if message.embeds:
            embed.add_field(
                name="⚠️ 注意",
                value="原文包含 embed 內容，請查看原始訊息",
                inline=False
            )
        
        embed.set_footer(text=f" transplanted by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.followup.send("✅ 訊息已移植！", ephemeral=True)
    
    # ===== 鼓掌功能 =====
    @app_commands.context_menu(name="鼓掌")
    async def clap_context_menu(self, interaction: discord.Interaction, message: discord.Message):
        """給訊息作者鼓掌鼓勵"""
        # 不能對自己的訊息鼓掌
        if message.author == interaction.user:
            await interaction.response.send_message("❌ 你不能給自己鼓掌哦！", ephemeral=True)
            return
        
        # 檢查是否為機器人
        if message.author.bot:
            await interaction.response.send_message("❌ 不能給機器人鼓掌！", ephemeral=True)
            return
        
        # 隨機選擇鼓勵語
        cheer = random.choice(self.cheer_messages)
        
        # 創建 embed
        embed = discord.Embed(
            title="👏 鼓掌時間！",
            description=f"{interaction.user.mention} 給 {message.author.mention} 鼓掌！",
            color=0xf1c40f
        )
        
        embed.add_field(
            name="💪 鼓勵語",
            value=cheer,
            inline=False
        )
        
        # 添加訊息連結
        embed.add_field(
            name="📝 被鼓掌的訊息",
            value=f"[點擊查看]({message.jump_url})",
            inline=False
        )
        
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"鼓掌者：{interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        
        # 添加鼓掌反應
        try:
            await message.add_reaction("👏")
        except:
            pass
    
    # ===== Make it a quote 功能 =====
    @app_commands.context_menu(name="引用")
    async def quote_context_menu(self, interaction: discord.Interaction, message: discord.Message):
        """將訊息轉換為引用格式"""
        # 創建引用 embed
        embed = discord.Embed(
            title="💬 引用訊息",
            description=message.content or "*（此訊息只有附件或 embed）*",
            color=0x95a5a6,
            timestamp=message.created_at
        )
        
        # 添加作者資訊
        embed.set_author(
            name=f"{message.author.display_name} ({message.author})",
            icon_url=message.author.display_avatar.url
        )
        
        # 添加引用標記
        embed.add_field(
            name="📌 引用自",
            value=f"[原始訊息]({message.jump_url})",
            inline=False
        )
        
        # 如果有 embed，添加說明
        if message.embeds:
            embed.add_field(
                name="⚠️ 注意",
                value="原文包含 embed 內容",
                inline=False
            )
        
        embed.set_footer(text=f"引用者：{interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(ContextMenusCog(bot))