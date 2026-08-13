import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
from utils.i18n import t

class HttpCatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # 常見的 HTTP 狀態碼說明
        self.status_descriptions = {
            100: "Continue - 繼續",
            101: "Switching Protocols - 切換協議",
            200: "OK - 成功",
            201: "Created - 已建立",
            204: "No Content - 無內容",
            301: "Moved Permanently - 永久移動",
            302: "Found - 找到",
            304: "Not Modified - 未修改",
            400: "Bad Request - 錯誤的請求",
            401: "Unauthorized - 未授權",
            403: "Forbidden - 禁止訪問",
            404: "Not Found - 找不到",
            405: "Method Not Allowed - 方法不允許",
            408: "Request Timeout - 請求超時",
            409: "Conflict - 衝突",
            418: "I'm a teapot - 我是茶壺",
            429: "Too Many Requests - 請求過多",
            500: "Internal Server Error - 伺服器內部錯誤",
            502: "Bad Gateway - 閘道錯誤",
            503: "Service Unavailable - 服務不可用",
            504: "Gateway Timeout - 閘道超時"
        }
    
    @commands.hybrid_command(name='httpcat', aliases=['HTTP貓'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def httpcat(self, ctx, status_code: int = 200):
        """顯示 HTTP 狀態碼的可愛貓咪圖片"""
        gid = ctx.guild.id if ctx.guild else None
        # 驗證狀態碼範圍
        if status_code < 100 or status_code > 599:
            await ctx.send(t(gid, "httpcat.range"), ephemeral=True)
            return
        
        # 獲取狀態碼描述
        description = self.status_descriptions.get(status_code, "HTTP Status Code")
        
        # 構建圖片 URL
        image_url = f"https://http.cat/{status_code}"
        
        # 創建 embed
        embed = discord.Embed(
            title=f"🐱 HTTP {status_code}",
            description=description,
            color=0x3498db if status_code < 400 else 0xe74c3c
        )
        
        embed.set_image(url=image_url)
        embed.set_footer(text=t(gid, "httpcat.footer", user=ctx.author.display_name))
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(HttpCatCog(bot))