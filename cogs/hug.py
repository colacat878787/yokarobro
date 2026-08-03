import discord
from discord.ext import commands
from discord import app_commands
import random

class HugCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # 可愛的抱抱動畫描述
        self.hug_animations = [
            "伸出可愛的小爪爪緊緊抱住你 🤗",
            "用軟綿綿的爪子環抱住你 💕",
            "輕輕地用爪子拍拍你的背 🐾",
            "用溫暖的小爪子給你一個大大的擁抱 ✨",
            "伸出毛茸茸的爪子緊緊摟住你 🥰",
            "用QQ的爪子輕輕抱著你搖啊搖 🎀",
            "伸出小手手給你一個溫暖的抱抱 🌸",
            "用軟軟的爪子緊緊纏住你 💝"
        ]
        
        # 可愛的 GIF 圖片 (使用 Discord emoji 或圖片連結)
        self.hug_gifs = [
            "https://media.giphy.com/media/lrr9rHuoWJdAI/giphy.gif",
            "https://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif",
            "https://media.giphy.com/media/3o7TKsQ8X3x8ZfH6gA/giphy.gif",
            "https://media.giphy.com/media/l2QDLvL2jHM7eX9Ac/giphy.gif"
        ]
    
    @commands.hybrid_command(name='抱抱', aliases=['hug', '擁抱'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def hug(self, ctx, target: discord.Member = None):
        """伸出可愛的小爪爪抱抱你或其他人
        
        使用方式：
        !抱抱          - 抱抱自己
        !抱抱 @用戶    - 抱抱指定用戶
        !hug @user     - 英文版本
        """
        # 如果沒有指定目標，就抱抱自己
        if target is None:
            target = ctx.author
        
        # 隨機選擇動畫描述
        animation = random.choice(self.hug_animations)
        
        # 創建 embed
        embed = discord.Embed(
            title="🐾 抱抱時間！",
            description=f"{ctx.author.mention} {animation}",
            color=0xffb6c1
        )
        
        # 添加目標用戶
        if target != ctx.author:
            embed.add_field(
                name="💝 傳送對象",
                value=f"{target.mention} 收到了滿滿的愛心！",
                inline=False
            )
        
        # 添加可愛的 footer
        embed.set_footer(text="✨ 洛洛的小爪子永遠為你敞開 ✨")
        
        # 發送 embed
        await ctx.send(embed=embed)
        
        # 有機率發送一個可愛的反應
        if random.random() < 0.3:  # 30% 機率
            try:
                await ctx.message.add_reaction("💕")
            except:
                pass

async def setup(bot):
    await bot.add_cog(HugCog(bot))