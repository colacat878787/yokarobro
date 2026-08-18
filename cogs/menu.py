import discord
from discord.ext import commands
from discord import app_commands
import random

class MenuView(discord.ui.View):
    """互動式選單面板"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🐾 抱抱", style=discord.ButtonStyle.primary, custom_id="menu_hug", emoji="🤗")
    async def hug_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """抱抱功能介紹"""
        embed = discord.Embed(
            title="🐾 抱抱功能",
            description="伸出可愛的小爪爪抱抱你！",
            color=0xffb6c1
        )
        embed.add_field(
            name="📝 使用方式",
            value="`!抱抱` - 抱抱自己\n`!抱抱 @用戶` - 抱抱指定用戶\n`/抱抱` - 使用斜線指令",
            inline=False
        )
        embed.add_field(
            name="✨ 特色",
            value="• 隨機可愛的動畫描述\n• 溫暖的愛心傳送\n• 30% 機率觸發愛心反應",
            inline=False
        )
        embed.set_footer(text="💕 洛洛的小爪子永遠為你敞開")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🎵 音樂", style=discord.ButtonStyle.success, custom_id="menu_music", emoji="🎧")
    async def music_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """音樂功能介紹"""
        embed = discord.Embed(
            title="🎵 音樂功能",
            description="享受高品質的音樂體驗！",
            color=0x2ecc71
        )
        embed.add_field(
            name="📝 主要指令",
            value="`!play [歌名]` - 播放音樂\n`!skip` - 跳過歌曲\n`!stop` - 停止播放\n`!queue` - 查看播放清單",
            inline=False
        )
        embed.add_field(
            name="✨ 特色功能",
            value="• 支援 YouTube/Spotify\n• 多音軌混音\n• 247 永不打烊模式\n• 反 Rickroll 護盾",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="💰 經濟", style=discord.ButtonStyle.success, custom_id="menu_economy", emoji="💵")
    async def economy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """經濟系統介紹"""
        embed = discord.Embed(
            title="💰 經濟系統",
            description="賺取、儲蓄、投資，成為洛洛幣大亨！",
            color=0xf1c40f
        )
        embed.add_field(
            name="📝 主要指令",
            value="`!錢包` - 查看資產\n`!打工` - 賺取洛洛幣\n`!簽到` - 每日獎勵\n`!賭博 [金額]` - 試試手氣",
            inline=False
        )
        embed.add_field(
            name="✨ 特色功能",
            value="• 銀行存款系統\n• 信用卡功能\n• 股票市場交易\n• 每日簽到抽卡",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🎮 遊戲", style=discord.ButtonStyle.primary, custom_id="menu_games", emoji="🎲")
    async def games_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """遊戲功能介紹"""
        embed = discord.Embed(
            title="🎮 遊戲與娛樂",
            description="各種好玩的遊戲等你來挑戰！",
            color=0x9b59b6
        )
        embed.add_field(
            name="📝 遊戲指令",
            value="`!一番賞` - 抽星空一番賞\n`!抽卡` - 收集稀有卡片\n`!狼人殺` - 經典桌遊\n`!運勢` - 每日籤詩",
            inline=False
        )
        embed.add_field(
            name="✨ 特色",
            value="• 卡片收集系統\n• 稀有頭銜獎勵\n• 多人互動遊戲\n• 每日運勢占卜",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🛡️ 管理", style=discord.ButtonStyle.danger, custom_id="menu_admin", emoji="⚙️")
    async def admin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """管理功能介紹"""
        embed = discord.Embed(
            title="🛡️ 管理員功能",
            description="強大的管理工具，讓伺服器運作更順暢！",
            color=0xe74c3c
        )
        embed.add_field(
            name="📝 管理指令",
            value="`!後台` - 圖形化管理面板\n`!設定驗證` - 設定入群驗證\n`!開單` - 票單系統\n`!備份` - 伺服器備份",
            inline=False
        )
        embed.add_field(
            name="✨ 特色功能",
            value="• 視覺化控制面板\n• 自動備份系統\n• 權限管理\n• 審核日誌記錄",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📊 等級", style=discord.ButtonStyle.secondary, custom_id="menu_levels", emoji="⭐")
    async def levels_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """等級系統介紹"""
        embed = discord.Embed(
            title="📊 等級與經驗值",
            description="聊天獲得經驗，升級解鎖更多功能！",
            color=0x3498db
        )
        embed.add_field(
            name="📝 相關指令",
            value="`!等級` - 查看等級卡片\n`!排行榜` - 查看排名\n`!每日簽到` - 獲得獎勵",
            inline=False
        )
        embed.add_field(
            name="✨ 特色",
            value="• 精美等級卡片\n• 全球排行榜\n• 連續簽到獎勵\n• 特殊頭銜解鎖",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="💬 其他", style=discord.ButtonStyle.secondary, custom_id="menu_other", emoji="📦")
    async def other_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """其他功能介紹"""
        embed = discord.Embed(
            title="💬 其他實用功能",
            description="更多有趣的功能等你發掘！",
            color=0x95a5a6
        )
        embed.add_field(
            name="📝 實用指令",
            value="`!天氣 [城市]` - 查詢天氣\n`!維基 [關鍵字]` - 搜尋維基\n`!截圖 [網址]` - 網頁截圖\n`!翻譯` - 外星文翻譯\n`!rr` - 反應角色設定\n`!afk` - 設定離開狀態\n`!remindme` - 設定提醒\n`!starboard` - 星板功能\n`!autorole` - 自動身分組",
            inline=False
        )
        embed.add_field(
            name="✨ 特色",
            value="• 天氣預報\n• 維基百科搜尋\n• 網頁截圖\n• 多語言翻譯\n• 反應角色\n• AFK 自動回覆\n• 定時提醒\n• 星板熱門訊息",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MenuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name='選單', aliases=['menu'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def menu(self, ctx):
        """顯示互動式功能選單面板"""
        embed = discord.Embed(
            title="🎯 洛洛功能選單",
            description="點擊下方按鈕查看各項功能的詳細介紹！\n\n"
                        "💡 **提示**：所有功能都支援 `!指令` 和 `/指令` 兩種使用方式",
            color=0xffc0cb
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(
            name="🚀 快速開始",
            value="• 點擊按鈕查看功能說明\n• 按照說明使用指令\n• 享受洛洛帶來的樂趣！",
            inline=False
        )
        embed.set_footer(text="✨ 洛洛會一直陪伴著你哦～")
        
        await ctx.send(embed=embed, view=MenuView())


async def setup(bot):
    await bot.add_cog(MenuCog(bot))