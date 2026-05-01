import discord
from discord.ext import commands
import json, os, time

FINANCE_FILE = "finance_data.json"

class FinanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self._load()

    def _load(self):
        if os.path.exists(FINANCE_FILE):
            try:
                with open(FINANCE_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: pass
        return {}

    def _save(self):
        with open(FINANCE_FILE, "w", encoding="utf-8") as f: json.dump(self.data, f, indent=4)

    def get_user_data(self, uid):
        uid = str(uid)
        if uid not in self.data:
            self.data[uid] = {
                "has_card": False,
                "credit_limit": 1000000,
                "used_credit": 0,
                "is_frozen": False
            }
        return self.data[uid]

    @commands.hybrid_command(name="辦卡", description="辦理一張 Yokaro 黑金信用卡 (費用 $50,000)")
    async def apply_card(self, ctx):
        uid = str(ctx.author.id)
        eco = self.bot.get_cog("EconomyCog")
        user_fin = self.get_user_data(uid)

        if user_fin["has_card"]:
            return await ctx.send("💳 您已經擁有一張信用卡了！")
        
        if eco.get_balance(uid) < 50000:
            return await ctx.send("❌ 餘額不足以支付辦卡工本費 ($50,000)！")

        eco.add_money(uid, -50000)
        user_fin["has_card"] = True
        self._save()
        
        embed = discord.Embed(title="💳 辦卡成功！", description=f"恭喜 {ctx.author.mention} 獲得 **Yokaro 黑金信用卡**！\n\n🔹 **信用額度:** $1,000,000\n🔹 **使用方式:** 當餘額不足時將自動由信用卡預支。", color=0x2f3136)
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/633/633611.png")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="信用額度", description="查詢您的信用卡狀態")
    async def credit_status(self, ctx):
        uid = str(ctx.author.id)
        user_fin = self.get_user_data(uid)
        
        if not user_fin["has_card"]:
            return await ctx.send("❌ 您尚未辦理信用卡，請使用 `/辦卡`。")

        remaining = user_fin["credit_limit"] - user_fin["used_credit"]
        status = "🔴 已刷爆/凍結" if user_fin["is_frozen"] or remaining <= 0 else "🟢 正常"
        
        embed = discord.Embed(title="💳 信用卡帳單中心", color=0x3498db)
        embed.add_field(name="狀態", value=status, inline=False)
        embed.add_field(name="總額度", value=f"${user_fin['credit_limit']:,}", inline=True)
        embed.add_field(name="已使用", value=f"${user_fin['used_credit']:,}", inline=True)
        embed.add_field(name="剩餘可用", value=f"${remaining:,}", inline=True)
        
        if user_fin["used_credit"] > 0:
            embed.set_footer(text="請及時還款，以免卡片被凍結！")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="還款", description="清償您的信用卡債務")
    async def pay_debt(self, ctx, amount: int):
        uid = str(ctx.author.id)
        eco = self.bot.get_cog("EconomyCog")
        user_fin = self.get_user_data(uid)

        if not user_fin["has_card"]: return await ctx.send("❌ 您沒有信用卡。")
        if amount <= 0: return await ctx.send("❌ 輸入金額無效。")
        
        balance = eco.get_balance(uid)
        if balance < amount: return await ctx.send("❌ 錢包餘額不足以還款！")

        pay_actual = min(amount, user_fin["used_credit"])
        if pay_actual <= 0: return await ctx.send("✅ 您目前沒有欠債喔！")

        eco.add_money(uid, -pay_actual)
        user_fin["used_credit"] -= pay_actual
        if user_fin["used_credit"] < user_fin["credit_limit"]:
            user_fin["is_frozen"] = False
            
        self._save()
        await ctx.send(f"✅ 還款成功！您已償還 ${pay_actual:,} 元。目前剩餘債務: ${user_fin['used_credit']:,}")

    # 提供給其他模組呼叫的 API
    def charge(self, uid, amount):
        uid = str(uid)
        user_fin = self.get_user_data(uid)
        
        if not user_fin["has_card"]: return False, "No card"
        if user_fin["is_frozen"]: return False, "Card frozen"
        
        remaining = user_fin["credit_limit"] - user_fin["used_credit"]
        if remaining < amount:
            user_fin["is_frozen"] = True
            self._save()
            return False, "Maxed out"
            
        user_fin["used_credit"] += amount
        self._save()
        return True, "Success"

async def setup(bot):
    await bot.add_cog(FinanceCog(bot))
