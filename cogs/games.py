import discord
from discord.ext import commands
import aiohttp
import json

class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pjsk_api = "https://api.sekai.best/api/user/{user_id}/profile"

    @commands.command(name='pjsekai', aliases=['pjsk', '世界計畫'])
    async def pjsekai(self, ctx, user_id: str = None):
        """查詢 Project Sekai (世界計畫) 玩家資訊"""
        if not user_id:
            return await ctx.send("❓ 請提供玩家 ID 喔！例如：`!pjsekai 1234567890`")

        async with ctx.typing():
            url = self.pjsk_api.format(user_id=user_id)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            user = data.get('user', {})
                            
                            # 提取基本資訊
                            name = user.get('name', '未知玩家')
                            rank = user.get('rank', 0)
                            comment = user.get('word', '無簡介')
                            user_id_display = user.get('userId', user_id)
                            
                            embed = discord.Embed(
                                title=f"🎵 Project Sekai 玩家檔案",
                                color=0x33ccff
                            )
                            embed.add_field(name="👤 玩家名稱", value=name, inline=True)
                            embed.add_field(name="⭐ 等級 (Rank)", value=str(rank), inline=True)
                            embed.add_field(name="🆔 玩家 ID", value=str(user_id_display), inline=False)
                            embed.add_field(name="📝 簡介", value=comment, inline=False)
                            
                            # 活動排名資訊 (如果有)
                            rankings = data.get('rankings', [])
                            if rankings:
                                top_rank = rankings[0]
                                embed.add_field(
                                    name="🏆 活動紀錄", 
                                    value=f"當前/最近活動排名: {top_rank.get('rank', 'N/A')}", 
                                    inline=False
                                )
                            
                            embed.set_footer(text="Data provided by sekai.best")
                            embed.set_thumbnail(url="https://miku.ci/icon.png") # 預設頭像
                            
                            await ctx.send(embed=embed)
                        elif response.status == 404:
                            await ctx.send(f"❌ 找不到 ID 為 `{user_id}` 的玩家，請確認 ID 是否正確。")
                        else:
                            await ctx.send(f"❌ API 發生錯誤 (代碼: {response.status})，請稍後再試。")
            except Exception as e:
                print(f"PJSK Error: {e}")
                await ctx.send("嗷嗷嗷～連接 API 時發生意外了，請稍後再試！")

async def setup(bot):
    await bot.add_cog(GamesCog(bot))
