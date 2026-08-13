import discord
from discord.ext import commands
import random
import datetime
import asyncio
from utils.i18n import t

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='fortune', aliases=['運勢'])
    async def fortune(self, ctx):
        """每日抽籤"""
        gid = ctx.guild.id if ctx.guild else None
        fortunes = [
            t(gid, "fun.fortune.daiji"),
            t(gid, "fun.fortune.ji"),
            t(gid, "fun.fortune.chuuji"),
            t(gid, "fun.fortune.shoji"),
            t(gid, "fun.fortune.matsuji"),
            t(gid, "fun.fortune.matsu_shoji"),
            t(gid, "fun.fortune.kyo"),
            t(gid, "fun.fortune.daikyo"),
        ]
        colors = [0xe74c3c, 0xf1c40f, 0x2ecc71, 0x3498db, 0x9b59b6, 0x95a5a6, 0x34495e, 0x000000]

        # 根據日期與使用者 ID 計算固定的結果
        seed = int(datetime.date.today().strftime("%Y%m%d")) + ctx.author.id
        random.seed(seed)

        fi = random.randint(0, len(fortunes)-1)
        res = fortunes[fi]
        color = colors[fi]

        descriptions = {
            fortunes[0]: t(gid, "fun.fortune.daiji_d"),
            fortunes[1]: t(gid, "fun.fortune.ji_d"),
            fortunes[2]: t(gid, "fun.fortune.chuuji_d"),
            fortunes[3]: t(gid, "fun.fortune.shoji_d"),
            fortunes[4]: t(gid, "fun.fortune.matsuji_d"),
            fortunes[5]: t(gid, "fun.fortune.matsu_shoji_d"),
            fortunes[6]: t(gid, "fun.fortune.kyo_d"),
            fortunes[7]: t(gid, "fun.fortune.daikyo_d"),
        }

        embed = discord.Embed(
            title=t(gid, "fun.fortune.title", user=ctx.author.display_name),
            description=t(gid, "fun.fortune.result", res=res),
            color=color,
        )
        embed.add_field(name=t(gid, "fun.fortune.advice"), value=descriptions[res])
        embed.set_footer(text=t(gid, "fun.fortune.date", date=datetime.date.today()))
        await ctx.send(embed=embed)
        random.seed() # reset random seeds

    @commands.command(name='slot', aliases=['拉霸'])
    async def slot(self, ctx):
        """拉霸機"""
        gid = ctx.guild.id if ctx.guild else None
        items = ["🍒", "🍋", "🍇", "💎", "7️⃣", "🔔", "⭐"]
        result = [random.choice(items) for _ in range(3)]

        embed = discord.Embed(title=t(gid, "fun.slot.title"), color=0x3498db)
        embed.add_field(name=t(gid, "fun.slot.result"), value=f"| {result[0]} | {result[1]} | {result[2]} |", inline=False)

        if result[0] == result[1] == result[2]:
            embed.color = 0xf1c40f
            msg = t(gid, "fun.slot.jackpot")
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            embed.color = 0x2ecc71
            msg = t(gid, "fun.slot.small")
        else:
            msg = t(gid, "fun.slot.again")

        embed.set_footer(text=t(gid, "fun.slot.footer", user=ctx.author.display_name))
        await ctx.send(content=msg, embed=embed)

    @commands.command(name='giveaway', aliases=['抽獎'])
    async def giveaway(self, ctx, duration: int, *, prize: str):
        """抽獎功能"""
        gid = ctx.guild.id if ctx.guild else None
        embed = discord.Embed(
            title=t(gid, "fun.giveaway.title"),
            description=t(gid, "fun.giveaway.desc", prize=prize, duration=duration),
            color=0x9b59b6,
        )
        embed.set_footer(text=t(gid, "fun.giveaway.footer", user=ctx.author.display_name))
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
                await ctx.send(t(gid, "fun.giveaway.none"))
                return

            winner = random.choice(users)
            await ctx.send(t(gid, "fun.giveaway.winner", user=winner.mention, prize=prize))

        except Exception as e:
            print(f"抽獎發送失敗: {e}")
            await ctx.send(t(gid, "fun.giveaway.error"))

    @commands.hybrid_command(name='對話框', description='隨機傳送一個超好笑的對話框影片')
    async def duihuakuang(self, ctx):
        """隨機傳送對話框影片"""
        gid = ctx.guild.id if ctx.guild else None
        import os
        video_dir = "/home/container/duihuakuang"

        if not os.path.exists(video_dir):
            return await ctx.send(t(gid, "fun.duihua.notfound", path=video_dir), ephemeral=True)

        files = [f for f in os.listdir(video_dir) if os.path.isfile(os.path.join(video_dir, f))]
        # 過濾常見影片格式
        video_files = [f for f in files if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm'))]

        if not video_files:
            return await ctx.send(t(gid, "fun.duihua.novideo"), ephemeral=True)

        target_video = random.choice(video_files)
        video_path = os.path.join(video_dir, target_video)

        await ctx.send(file=discord.File(video_path))

async def setup(bot):
    await bot.add_cog(FunCog(bot))
