import discord
from discord.ext import commands
from discord import app_commands
import json, os, random, asyncio

KUJI_FILE = "kuji.json"
PREMIUM_FILE = "premium_users.json"
ADMIN_IDS = [1113353915010920452, 501251225715474433]

class RestockView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="♻️ 立即補貨 (基本盤)", style=discord.ButtonStyle.success)
    async def restock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in ADMIN_IDS: return await interaction.response.send_message("❌ 您無權補貨。", ephemeral=True)
        self.cog.pool = self.cog._default_pool()
        self.cog._save()
        await interaction.response.send_message("✅ 獎池已重新補貨！", ephemeral=True)

class KujiView(discord.ui.View):
    def __init__(self, economy_cog):
        super().__init__(timeout=None)
        self.economy_cog = economy_cog

    @discord.ui.button(label="🎲 立即抽賞 (單抽 $500)", style=discord.ButtonStyle.primary, custom_id="kuji_draw")
    async def draw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        
        if self.economy_cog.get_balance(uid) < 500:
            return await interaction.edit_original_response(content="嗷嗷嗷～錢包不夠 $500 喔！")

        kuji_cog = self.economy_cog.bot.get_cog("KujiCog")
        if not kuji_cog: return await interaction.edit_original_response(content="❌ 系統未啟動！")
            
        prize = kuji_cog.draw_prize()
        if not prize:
            return await interaction.edit_original_response(content="😱 本輪一番賞已完售！管理員已收到通知進行補貨。")

        # 扣錢與派獎
        self.economy_cog.add_money(uid, -500)
        kuji_cog.grant_prize(interaction.user, prize)
        
        msg = await interaction.followup.send(f"🌌 {interaction.user.mention} 正在從星空箱抽取...")
        await asyncio.sleep(1.5)

        embed = discord.Embed(title="🎊 恭喜中獎！", description=f"{interaction.user.mention} 抽中了：\n\n✨ **【 {prize} 】** ✨", color=0xf1c40f if "Premium" in prize else 0x3498db)
        embed.set_footer(text="獎勵已自動派發！")
        await msg.edit(content=None, embed=embed)
        await interaction.edit_original_response(content="✅ 抽賞完成！")

class KujiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = self._load()
        self.premium_users = self._load_premium()
        self.bot.add_view(KujiView(self.bot.get_cog("EconomyCog")))

    def _load(self):
        if os.path.exists(KUJI_FILE):
            try:
                with open(KUJI_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return self._default_pool()

    def _load_premium(self):
        if os.path.exists(PREMIUM_FILE):
            try:
                with open(PREMIUM_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return []

    def _default_pool(self):
        # 重新定義高格調獎池
        items = (["💎 SP賞: Yokaro Premium 永久會員"] * 1 +
                 ["💰 A賞: 50,000 卡洛幣"] * 2 +
                 ["💰 B賞: 20,000 卡洛幣"] * 5 +
                 ["💰 C賞: 10,000 卡洛幣"] * 10 +
                 ["🧧 D賞: 5,000 卡洛幣"] * 20 +
                 ["🧧 E賞: 1,000 卡洛幣"] * 42)
        return items

    def _save(self):
        with open(KUJI_FILE, "w", encoding="utf-8") as f: json.dump(self.pool, f, indent=2)
        with open(PREMIUM_FILE, "w", encoding="utf-8") as f: json.dump(self.premium_users, f)

    def draw_prize(self):
        if not self.pool: return None
        prize = random.choice(self.pool)
        self.pool.remove(prize)
        self._save()
        
        if not self.pool: # 完售通知管理員
            asyncio.create_task(self.notify_admins())
        return prize

    async def notify_admins(self):
        for aid in ADMIN_IDS:
            try:
                admin = await self.bot.fetch_user(aid)
                view = RestockView(self)
                await admin.send("🚨 **[一番賞預警]** 大總裁，目前一番賞獎池已經完售了！請點擊下方按鈕進行補貨。", view=view)
            except: pass

    def grant_prize(self, user, prize):
        uid = str(user.id)
        eco = self.bot.get_cog("EconomyCog")
        if "Premium" in prize:
            if user.id not in self.premium_users:
                self.premium_users.append(user.id)
                self._save()
        elif "卡洛幣" in prize:
            amount = int(re.search(r'\d+', prize.replace(',', '')).group())
            if eco: eco.add_money(uid, amount)

    def is_premium(self, user_id):
        return user_id in self.premium_users or user_id in ADMIN_IDS

    @commands.hybrid_command(name='一番賞')
    async def kuji_status(self, ctx):
        if not self.pool: return await ctx.send("😱 本輪已完售！已通知管理員補貨。")
        stats = {}
        for item in self.pool: stats[item] = stats.get(item, 0) + 1
        desc = "**目前剩餘獎項：**\n```\n" + "\n".join([f"{k}: {v}" for k, v in sorted(stats.items())]) + "```"
        embed = discord.Embed(title="🎟️ Yokaro Premium 一番賞", description=desc, color=0x3498db)
        await ctx.send(embed=embed, view=KujiView(self.bot.get_cog("EconomyCog")))

import re
async def setup(bot):
    await bot.add_cog(KujiCog(bot))
