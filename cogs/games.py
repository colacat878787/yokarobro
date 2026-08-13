import discord
from discord.ext import commands
import aiohttp
import json
from utils.i18n import t

class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pjsk_api = "https://api.sekai.best/api/user/{user_id}/profile"

    @commands.command(name='pjsekai', aliases=['pjsk', '世界計畫'])
    async def pjsekai(self, ctx, user_id: str = None):
        """查詢 Project Sekai (世界計畫) 玩家資訊 (目前支援日服)"""
        gid = ctx.guild.id if ctx.guild else None
        if not user_id:
            embed = discord.Embed(
                title=t(gid, "games.pjsk.howto"),
                description=t(gid, "games.pjsk.howto_desc"),
                color=0xffcc00
            )
            embed.add_field(name=t(gid, "games.pjsk.usage"), value="`!pjsekai <遊戲ID>`", inline=False)
            embed.add_field(name=t(gid, "games.pjsk.where"), value="進入遊戲 -> 選單 -> 簡介 (Profile) -> 右下角有一串數字。", inline=False)
            embed.set_footer(text=t(gid, "games.pjsk.footer"))
            return await ctx.send(embed=embed)

        if not user_id.isdigit():
            return await ctx.send(t(gid, "games.pjsk.ndigits"))

        async with ctx.typing():
            url = self.pjsk_api.format(user_id=user_id)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            user = data.get('user', {})
                            
                            name = user.get('name', t(gid, "games.pjsk.unknown_player"))
                            rank = user.get('rank', 0)
                            comment = user.get('word', t(gid, "games.pjsk.nocomment"))
                            
                            embed = discord.Embed(
                                title=f"🎵 Project Sekai - {name}",
                                url=f"https://sekai.best/user/{user_id}",
                                color=0x33ccff
                            )
                            embed.add_field(name=t(gid, "games.pjsk.field_name"), value=f"**{name}**", inline=True)
                            embed.add_field(name=t(gid, "games.pjsk.field_rank"), value=f"Rank {rank}", inline=True)
                            embed.add_field(name=t(gid, "games.pjsk.field_id"), value=f"`{user_id}`", inline=False)
                            
                            # 活動排名
                            rankings = data.get('rankings', [])
                            if rankings:
                                event = rankings[0]
                                embed.add_field(
                                    name=t(gid, "games.pjsk.field_event"),
                                    value=t(gid, "games.pjsk.rank_place", rank=event.get('rank', 'N/A')),
                                    inline=False
                                )
                            
                            embed.add_field(
                                name=t(gid, "games.pjsk.field_bio"),
                                value=comment if comment else t(gid, "games.pjsk.mystery"),
                                inline=False
                            )
                            embed.set_footer(text=t(gid, "games.pjsk.footer"))
                            embed.set_thumbnail(url="https://miku.ci/icon.png")
                            
                            await ctx.send(embed=embed)
                        elif response.status == 404:
                            await ctx.send(t(gid, "games.pjsk.notfound", uid=user_id))
                        else:
                            await ctx.send(t(gid, "games.pjsk.api_error", code=response.status))
            except Exception as e:
                print(f"PJSK Error: {e}")
                await ctx.send(t(gid, "games.pjsk.fatal"))

async def setup(bot):
    await bot.add_cog(GamesCog(bot))
