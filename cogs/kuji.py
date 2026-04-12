import discord
from discord.ext import commands
import json
import os
import random
import asyncio

KUJI_FILE = "kuji.json"

class KujiView(discord.ui.View):
    def __init__(self, economy_cog):
        super().__init__(timeout=60)
        self.economy_cog = economy_cog

    @discord.ui.button(label="🎲 立即抽賞 (單抽 $200)", style=discord.ButtonStyle.primary)
    async def draw_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if self.economy_cog.get_balance(user_id) < 200:
            await interaction.response.send_message("嗷嗷嗷～你的錢包不夠支付抽賞費用 ($200) 喔！", ephemeral=True)
            return

        # 讀取獎池
        kuji_cog = self.economy_cog.bot.get_cog("KujiCog")
        prize = kuji_cog.draw_prize()
        
        if not prize:
            await interaction.response.send_message("😱 糟糕！本輪一番賞已經被抽完了！請期待管理員重置獎池。嗷嗚...", ephemeral=True)
            return

        # 扣錢
        self.economy_cog.add_money(user_id, -200)
        
        # 視覺效果: 0.1s 反應先 defer 或直接回應
        await interaction.response.defer(ephemeral=False)
        
        msg = await interaction.followup.send(f"🌌 {interaction.user.mention} 正在從星空箱中抽取一張賞金券...")
        await asyncio.sleep(1)
        
        # 根據獎項分等級顯色
        color = 0x95a5a6
        if "A賞" in prize: color = 0xf1c40f
        elif "B賞" in prize: color = 0xe67e22
        elif "C賞" in prize: color = 0x9b59b6
        
        embed = discord.Embed(title="🎊 抽賞結果揭曉！", description=f"恭喜 {interaction.user.mention} 抽中了：\n\n✨ **【 {prize} 】** ✨", color=color)
        embed.set_footer(text=f"剩餘獎金目前顯示在 !一番賞 中 | 已自動扣除 $200")
        
        await msg.edit(content=None, embed=embed)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ 一番賞系統發生錯誤: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ 一番賞系統發生錯誤: {error}", ephemeral=True)

class KujiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = self.load_pool()

    def load_pool(self):
        if os.path.exists(KUJI_FILE):
            with open(KUJI_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return self.get_default_pool()

    def get_default_pool(self):
        # 預設獎池配置
        items = []
        items.extend(["A賞: 限定奢華頭像框"] * 1)
        items.extend(["B賞: 10000 虛擬幣"] * 2)
        items.extend(["C賞: 5000 虛擬幣"] * 5)
        items.extend(["D賞: 洛洛的親筆簽名畫"] * 10)
        items.extend(["E賞: 1000 虛擬幣"] * 20)
        items.extend(["F賞: 安慰獎 (100幣)"] * 42)
        items.append("LastOne賞: 究極稀有稱號") # 最後一抽的人額外獲得，這裡邏輯簡化為獎池最後一項
        return items

    def save_pool(self):
        with open(KUJI_FILE, "w", encoding="utf-8") as f:
            json.dump(self.pool, f, indent=4)

    def draw_prize(self):
        if not self.pool: return None
        prize = random.choice(self.pool)
        self.pool.remove(prize)
        self.save_pool()
        return prize

    @commands.command(name='一番賞', aliases=['kuji'])
    async def kuji_status(self, ctx):
        """查看一番賞獎池剩餘狀況"""
        if not self.pool:
            await ctx.send("😱 本輪一番賞已完售！請敲碗管理員重置獎池。嗷嗚～")
            return

        # 統計獎項
        stats = {}
        for item in self.pool:
            stats[item] = stats.get(item, 0) + 1
        
        description = "目前的獎池剩餘量：\n```\n"
        for item, count in sorted(stats.items()):
            description += f"{item}: {count} 個\n"
        description += f"\n總計剩餘: {len(self.pool)} 個項目\n```"
        
        embed = discord.Embed(title="🎟️ Yokaro 星空一番賞現況", description=description, color=0x3498db)
        embed.set_footer(text="單抽只需 $200！祝您好運。嗷嗷嗷～")
        
        economy_cog = self.bot.get_cog("EconomyCog")
        view = KujiView(economy_cog)
        await ctx.send(embed=embed, view=view)

    @commands.command(name='重置一番賞')
    @commands.has_permissions(administrator=True)
    async def kuji_reset(self, ctx):
        """(管理員) 重置全國一番賞獎池"""
        self.pool = self.get_default_pool()
        self.save_pool()
        await ctx.send("♻️ **一番賞獎池已重新補貨完畢！** 大家可以開始瘋狂抽獎囉！嗷嗷嗷～")

async def setup(bot):
    await bot.add_cog(KujiCog(bot))
