import discord
from discord.ext import commands
import random
import datetime
import asyncio

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='fortune', aliases=['運勢'])
    async def fortune(self, ctx):
        """每日抽籤"""
        fortunes = ["大吉", "吉", "中吉", "小吉", "末吉", "末小吉", "凶", "大凶"]
        colors = [0xe74c3c, 0xf1c40f, 0x2ecc71, 0x3498db, 0x9b59b6, 0x95a5a6, 0x34495e, 0x000000]
        
        # 根據日期與使用者 ID 計算固定的結果
        seed = int(datetime.date.today().strftime("%Y%m%d")) + ctx.author.id
        random.seed(seed)
        
        fi = random.randint(0, len(fortunes)-1)
        res = fortunes[fi]
        color = colors[fi]
        
        descriptions = {
            "大吉": "嗷嗷嗷！今天手氣超級好！買刮刮樂的最佳時機！",
            "吉": "今天是個充滿活力的一天，加油！",
            "中吉": "心情愉悅，一切都會順利的。",
            "小吉": "平穩安定的每一天，這也是種幸福呢。",
            "末吉": "快結束的今天也會有好事的，嗷～",
            "末小吉": "生活中有些微小的小確幸等著你。",
            "凶": "今天要注意點，別漏掉重要訊息喔。",
            "大凶": "嗷... 沒關係，再衰一次明天就會轉運了！"
        }
        
        embed = discord.Embed(title=f"🌸 {ctx.author.display_name} 的今日運勢", description=f"你的運氣是：**{res}**", color=color)
        embed.add_field(name="洛洛的叮嚀", value=descriptions[res])
        embed.set_footer(text=f"日期：{datetime.date.today()}")
        await ctx.send(embed=embed)
        random.seed() # reset random seeds

    @commands.command(name='slot', aliases=['拉霸'])
    async def slot(self, ctx):
        """拉霸機"""
        items = ["🍒", "🍋", "🍇", "💎", "7️⃣", "🔔", "⭐"]
        result = [random.choice(items) for _ in range(3)]
        
        embed = discord.Embed(title="🎰 優卡洛拉霸機 🎰", color=0x3498db)
        embed.add_field(name="結果", value=f"| {result[0]} | {result[1]} | {result[2]} |", inline=False)
        
        if result[0] == result[1] == result[2]:
            embed.color = 0xf1c40f
            msg = "⚡ **中大獎！！！** ⚡ 嗷嗷嗷嗷嗷嗷嗷！恭喜你！"
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            embed.color = 0x2ecc71
            msg = "✨ **小有驚喜！** ✨ 差一點點就大獎了！連中兩個！"
        else:
            msg = "嗷～再挑戰一次吧！相信下次一定能中的！"
            
        embed.set_footer(text=f"由 {ctx.author.display_name} 啟動")
        await ctx.send(content=msg, embed=embed)

    @commands.command(name='giveaway', aliases=['抽獎'])
    async def giveaway(self, ctx, duration: int, *, prize: str):
        """抽獎功能"""
        embed = discord.Embed(title="🎉 抽獎時間到！", description=f"獎品：**{prize}**\n時間：**{duration}** 秒\n\n點擊下方的 🎉 參與抽獎！", color=0x9b59b6)
        embed.set_footer(text=f"發起人：{ctx.author.display_name}")
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("🎉")
        
        await asyncio.sleep(duration)
        
        try:
            # 重新獲取訊息以取得最新反應
            new_msg = await ctx.channel.fetch_message(msg.id)
            
            users = []
            for reaction in new_msg.reactions:
                if str(reaction.emoji) == "🎉":
                    async for user in reaction.users():
                        if not user.bot:
                            users.append(user)
                            
            if len(users) == 0:
                await ctx.send(f"嗷～沒人參加抽獎嗎？那 **{prize}** 被洛洛自己拿走囉！")
                return
                
            winner = random.choice(users)
            await ctx.send(f"🎉 恭喜 {winner.mention} 抽中了 **{prize}**！")
            
        except Exception as e:
            print(f"抽獎發送失敗: {e}")
            await ctx.send("嗷～抽獎結算時發生了錯誤！")

async def setup(bot):
    await bot.add_cog(FunCog(bot))
