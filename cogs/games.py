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
        """查詢 Project Sekai (世界計畫) 玩家資訊 (目前支援日服)"""
        if not user_id:
            embed = discord.Embed(
                title="❓ 如何使用 pjsekai 指令",
                description="請提供您的 **Project Sekai 遊戲內 ID** (不是 Discord ID 喔！)",
                color=0xffcc00
            )
            embed.add_field(name="📌 用法", value="`!pjsekai <遊戲ID>`", inline=False)
            embed.add_field(name="🔍 哪裡找 ID？", value="進入遊戲 -> 選單 -> 簡介 (Profile) -> 右下角有一串數字。", inline=False)
            embed.set_footer(text="目前僅支援日服 (JP Server) 查詢")
            return await ctx.send(embed=embed)

        if not user_id.isdigit():
            return await ctx.send("❌ 遊戲 ID 應該只包含數字喔！")

        async with ctx.typing():
            url = self.pjsk_api.format(user_id=user_id)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            user = data.get('user', {})
                            
                            name = user.get('name', '未知玩家')
                            rank = user.get('rank', 0)
                            comment = user.get('word', '無簡介')
                            
                            embed = discord.Embed(
                                title=f"🎵 Project Sekai 玩家檔案 - {name}",
                                url=f"https://sekai.best/user/{user_id}",
                                color=0x33ccff
                            )
                            embed.add_field(name="👤 玩家名稱", value=f"**{name}**", inline=True)
                            embed.add_field(name="⭐ 等級 (Rank)", value=f"Rank {rank}", inline=True)
                            embed.add_field(name="🆔 遊戲 ID", value=f"`{user_id}`", inline=False)
                            
                            # 活動排名
                            rankings = data.get('rankings', [])
                            if rankings:
                                event = rankings[0]
                                embed.add_field(
                                    name="🏆 最近活動排名", 
                                    value=f"第 {event.get('rank', 'N/A')} 名", 
                                    inline=False
                                )
                            
                            embed.add_field(name="📝 簡介", value=comment if comment else "這個玩家很神祕，什麼都沒寫。", inline=False)
                            embed.set_footer(text="資料來源：sekai.best (JP Server)")
                            embed.set_thumbnail(url="https://miku.ci/icon.png")
                            
                            await ctx.send(embed=embed)
                        elif response.status == 404:
                            await ctx.send(f"❌ 找不到 ID 為 `{user_id}` 的玩家。\n\n💡 **小提示**：\n1. 目前僅支援 **日服 (JP Server)** 查詢。\n2. 請確認這不是 Discord ID。\n3. 如果是剛創的新號，API 可能還沒同步喔！")
                        else:
                            await ctx.send(f"❌ API 暫時沒反應 (代碼: {response.status})，洛洛待會再試！")
            except Exception as e:
                print(f"PJSK Error: {e}")
                await ctx.send("嗷嗷嗷～API 壞掉惹，洛洛修不完嗚嗚...")

async def setup(bot):
    await bot.add_cog(GamesCog(bot))
