import discord
from discord.ext import commands
import json, os, random, time, hashlib

ECONOMY_FILE = "economy.json"

# ──────────────────────────────────────────
#  ATM Modals
# ──────────────────────────────────────────
class PasswordModal(discord.ui.Modal, title="🔑 輸入密碼"):
    password = discord.ui.TextInput(label="密碼（4-6位數）", placeholder="請輸入你的銀行密碼", min_length=4, max_length=6, style=discord.TextStyle.short)

    def __init__(self, economy_cog, mode):
        super().__init__()
        self.economy_cog = economy_cog
        self.mode = mode  # "register" or "login"

    async def on_submit(self, interaction: discord.Interaction):
        # 1. 立即進入思考模式
        await interaction.response.defer(ephemeral=True)
        
        uid = str(interaction.user.id)
        data = self.economy_cog.get_user_data(uid)
        hashed = hashlib.sha256(self.password.value.encode()).hexdigest()
        
        if self.mode == "register":
            data["password"] = hashed
            self.economy_cog.save_data()
            await interaction.edit_original_response(content="✅ 開戶完成！請重新使用 `!ATM` 並選擇登入。")

        elif self.mode == "login":
            if data.get("password") == hashed:
                view = ATMLoggedInView(interaction.user, self.economy_cog)
                embed = discord.Embed(title="🏦 洛洛銀行 — 已登入", description="請選擇服務：", color=0x2ecc71)
                embed.add_field(name="💛 錢包", value=f"${data['balance']}")
                embed.add_field(name="🏦 銀行", value=f"${data.get('bank', 0)}")
                await interaction.edit_original_response(content=None, embed=embed, view=view)
            else:
                await interaction.edit_original_response(content="❌ 密碼錯誤！請重試。")

class AmountModal(discord.ui.Modal):
    amount = discord.ui.TextInput(label="金額", placeholder="請輸入數字", style=discord.TextStyle.short)

    def __init__(self, economy_cog, user, mode):
        super().__init__(title="💰 存款" if mode == "deposit" else "💸 提款")
        self.economy_cog = economy_cog
        self.user = user
        self.mode = mode

    async def on_submit(self, interaction: discord.Interaction):
        # 1. 立即進入思考模式
        await interaction.response.defer(ephemeral=True)
        
        try:
            amt = int(self.amount.value)
            if amt <= 0: raise ValueError
        except ValueError:
            await interaction.edit_original_response(content="❌ 請輸入有效的正整數金額！")
            return

        uid = str(self.user.id)
        data = self.economy_cog.get_user_data(uid)

        if self.mode == "deposit":
            if data["balance"] < amt:
                await interaction.edit_original_response(content=f"❌ 錢包不足(${ data['balance']})！")
                return
            data["balance"] -= amt
            data["bank"] = data.get("bank", 0) + amt
            self.economy_cog.save_data()
            await interaction.edit_original_response(content=f"✅ 存入 **${amt}**！銀行餘額：**${data['bank']}**")

        elif self.mode == "withdraw":
            bank = data.get("bank", 0)
            if bank < amt:
                await interaction.edit_original_response(content=f"❌ 銀行存款不足(${bank})！")
                return
            data["bank"] -= amt
            data["balance"] += amt
            self.economy_cog.save_data()
            await interaction.edit_original_response(content=f"✅ 提領 **${amt}**！錢包餘額：**${data['balance']}**")

# ──────────────────────────────────────────
#  ATM Views
# ──────────────────────────────────────────
class ATMMainView(discord.ui.View):
    def __init__(self, user, economy_cog):
        super().__init__(timeout=60)
        self.user = user
        self.economy_cog = economy_cog
        uid = str(user.id)
        data = economy_cog.get_user_data(uid)
        has_account = "password" in data

        if not has_account:
            btn = discord.ui.Button(label="🏦 立即開戶", style=discord.ButtonStyle.success)
            btn.callback = self.register_cb
            self.add_item(btn)
        else:
            btn = discord.ui.Button(label="🔑 登入銀行", style=discord.ButtonStyle.primary)
            btn.callback = self.login_cb
            self.add_item(btn)

    async def register_cb(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PasswordModal(self.economy_cog, "register"))

    async def login_cb(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PasswordModal(self.economy_cog, "login"))

    async def on_error(self, interaction, error, item):
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ ATM錯誤: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ ATM錯誤: {error}", ephemeral=True)

class ATMLoggedInView(discord.ui.View):
    def __init__(self, user, economy_cog):
        super().__init__(timeout=60)
        self.user = user
        self.economy_cog = economy_cog

    @discord.ui.button(label="💰 存錢", style=discord.ButtonStyle.secondary)
    async def deposit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AmountModal(self.economy_cog, self.user, "deposit"))

    @discord.ui.button(label="💸 提款", style=discord.ButtonStyle.danger)
    async def withdraw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AmountModal(self.economy_cog, self.user, "withdraw"))

    @discord.ui.button(label="📄 查餘額", style=discord.ButtonStyle.primary)
    async def check(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 立即進入思考模式
        await interaction.response.defer(ephemeral=True)
        
        data = self.economy_cog.get_user_data(str(self.user.id))
        embed = discord.Embed(title="📄 帳戶資訊", color=0x3498db)
        embed.add_field(name="👛 錢包", value=f"${data['balance']}", inline=True)
        embed.add_field(name="🏦 銀行", value=f"${data.get('bank', 0)}", inline=True)
        
        # 處理完成後更新內容
        await interaction.edit_original_response(content=None, embed=embed)

    async def on_error(self, interaction, error, item):
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ ATM錯誤: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ ATM錯誤: {error}", ephemeral=True)

# ──────────────────────────────────────────
#  Work View
# ──────────────────────────────────────────
class WorkView(discord.ui.View):
    def __init__(self, user, economy_cog):
        super().__init__(timeout=30)
        self.user = user
        self.economy_cog = economy_cog

    @discord.ui.button(label="⛏️ 去挖礦", style=discord.ButtonStyle.primary)
    async def mine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._work(interaction, "挖礦", 100, 300)

    @discord.ui.button(label="🍔 去打工", style=discord.ButtonStyle.success)
    async def burger(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._work(interaction, "在漢堡店打工", 50, 200)

    @discord.ui.button(label="💻 去寫程式", style=discord.ButtonStyle.secondary)
    async def code(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._work(interaction, "寫程式", 150, 450)

    async def _work(self, interaction: discord.Interaction, job: str, mn: int, mx: int):
        # 1. 立即進入思考模式
        await interaction.response.defer(ephemeral=True)
        
        if interaction.user.id != self.user.id:
            await interaction.edit_original_response(content="❌ 這不是你的工作邀請喔！")
            return
            
        pay = random.randint(mn, mx)
        self.economy_cog.add_money(str(interaction.user.id), pay)
        bal = self.economy_cog.get_balance(str(interaction.user.id))
        
        embed = discord.Embed(title="💼 工作成果", color=discord.Color.green())
        embed.description = f"你剛剛去 **{job}**，賺到了 **${pay}**！嗷嗷嗷～"
        embed.set_footer(text=f"目前餘額: ${bal}")
        
        # 2. 處理完成後更新內容
        await interaction.edit_original_response(content=None, embed=embed, view=None)
        self.stop()

    async def on_error(self, interaction, error, item):
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ 工作錯誤: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ 工作錯誤: {error}", ephemeral=True)

# ──────────────────────────────────────────
#  Economy Cog
# ──────────────────────────────────────────
class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self._load()
        self.work_cd = {}

    def _load(self):
        if os.path.exists(ECONOMY_FILE):
            try:
                with open(ECONOMY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {}

    def save_data(self):
        with open(ECONOMY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def get_user_data(self, uid):
        if uid not in self.data:
            self.data[uid] = {"balance": 0, "bank": 0, "last_daily": 0}
        return self.data[uid]

    def get_balance(self, uid):
        return self.get_user_data(uid)["balance"]

    def add_money(self, uid, amt, bank=False):
        d = self.get_user_data(uid)
        if bank:
            d["bank"] = d.get("bank", 0) + amt
        else:
            d["balance"] += amt
        self.save_data()

    @commands.command(name='balance', aliases=['錢包', '餘額'])
    async def balance(self, ctx, member: discord.Member = None):
        m = member or ctx.author
        d = self.get_user_data(str(m.id))
        embed = discord.Embed(title=f"💰 {m.display_name} 的資產", color=0xf1c40f)
        embed.add_field(name="👛 錢包", value=f"**${d['balance']}**", inline=True)
        embed.add_field(name="🏦 銀行", value=f"**${d.get('bank',0)}**", inline=True)
        embed.set_thumbnail(url=m.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='ATM', aliases=['銀行'])
    async def atm(self, ctx):
        d = self.get_user_data(str(ctx.author.id))
        embed = discord.Embed(title="🏪 Yokaro 24h 自動櫃員機", description="歡迎使用洛洛銀行！請點選下方按鈕。", color=0x2ecc71)
        embed.set_footer(text="洛洛銀行，關心您的每一分錢 🐾")
        await ctx.send(embed=embed, view=ATMMainView(ctx.author, self))

    @commands.command(name='daily', aliases=['簽到'])
    async def daily(self, ctx):
        uid = str(ctx.author.id)
        d = self.get_user_data(uid)
        now = time.time()
        if now - d.get("last_daily", 0) < 86400:
            rem = 86400 - (now - d["last_daily"])
            await ctx.send(f"嗷～請再等 **{int(rem//3600)} 小時 {int((rem%3600)//60)} 分鐘** 喔！")
            return
        d["balance"] += 500
        d["last_daily"] = now
        self.save_data()
        await ctx.send(f"✨ 簽到成功！獲得 **$500**！目前錢包：**${d['balance']}**。")

    @commands.command(name='work', aliases=['工作'])
    async def work(self, ctx):
        uid = str(ctx.author.id)
        now = time.time()
        if uid in self.work_cd and now - self.work_cd[uid] < 600:
            await ctx.send(f"嗷～再等 **{int((600-(now-self.work_cd[uid]))//60)} 分鐘** 才能再工作！")
            return
        self.work_cd[uid] = now
        await ctx.send("💼 **選擇你要做的工作：**", view=WorkView(ctx.author, self))

    @commands.command(name='rps', aliases=['猜拳'])
    async def rps(self, ctx, choice: str, bet: int = 0):
        ch_map = {"剪刀":"✌️","石頭":"✊","布":"✋","scissors":"✌️","rock":"✊","paper":"✋"}
        norm = {"scissors":"剪刀","rock":"石頭","paper":"布"}
        c = choice.lower()
        if c not in ch_map:
            await ctx.send("嗷～請輸入：剪刀、石頭、布！"); return
        user_ch = norm.get(c, c)
        uid = str(ctx.author.id)
        if bet > self.get_balance(uid):
            await ctx.send("嗷嗷嗷～錢不夠喔！"); return
        bot_ch = random.choice(["剪刀","石頭","布"])
        embed = discord.Embed(title="🎮 猜拳!", color=0x9b59b6)
        embed.add_field(name="你", value=f"{ch_map[user_ch]} {user_ch}", inline=True)
        embed.add_field(name="洛洛", value=f"{ch_map[bot_ch]} {bot_ch}", inline=True)
        wins = {("石頭","剪刀"),("剪刀","布"),("布","石頭")}
        if user_ch == bot_ch:
            embed.description = "平手！嗷～"
        elif (user_ch, bot_ch) in wins:
            self.add_money(uid, bet)
            embed.description = f"你贏了！+**${bet}**！嗷嗷嗷～🎉"
            embed.color = 0x2ecc71
        else:
            self.add_money(uid, -bet)
            embed.description = f"洛洛贏了！-**${bet}**... 嗷嗚..."
            embed.color = 0xe74c3c
        if bet > 0:
            embed.set_footer(text=f"目前餘額: ${self.get_balance(uid)}")
        await ctx.send(embed=embed)

    @commands.command(name='gamble', aliases=['賭博'])
    async def gamble(self, ctx, bet: int):
        uid = str(ctx.author.id)
        if bet <= 0 or bet > self.get_balance(uid):
            await ctx.send("嗷～賭注有問題喔！"); return
        if random.random() > 0.52:
            self.add_money(uid, bet)
            await ctx.send(f"✨ **贏了！** +${bet}！目前：**${self.get_balance(uid)}**。嗷嗷嗷～")
        else:
            self.add_money(uid, -bet)
            await ctx.send(f"💀 **輸了！** -${bet}... 目前：**${self.get_balance(uid)}**。嗷嗚...")

    @commands.command(name='查帳', aliases=['check_account'])
    @commands.has_permissions(administrator=True)
    async def check_account(self, ctx, member: discord.Member):
        d = self.get_user_data(str(member.id))
        embed = discord.Embed(title=f"🕵️ 財務調查: {member.display_name}", color=0x34495e)
        embed.add_field(name="Wallet", value=f"${d['balance']}")
        embed.add_field(name="Bank", value=f"${d.get('bank',0)}")
        embed.add_field(name="有銀行帳戶", value="是" if "password" in d else "否")
        await ctx.send(embed=embed)

    @commands.command(name='撥款', aliases=['add_money_admin'])
    @commands.has_permissions(administrator=True)
    async def add_money_admin(self, ctx, member: discord.Member, amount: int, target="wallet"):
        self.add_money(str(member.id), amount, bank=(target.lower()=="bank"))
        await ctx.send(f"✅ 已為 {member.mention} 的 {'銀行' if target.lower()=='bank' else '錢包'} 注入 **${amount}**！")

    @commands.command(name='扣款', aliases=['remove_money_admin'])
    @commands.has_permissions(administrator=True)
    async def remove_money_admin(self, ctx, member: discord.Member, amount: int, target="wallet"):
        self.add_money(str(member.id), -amount, bank=(target.lower()=="bank"))
        await ctx.send(f"💸 已從 {member.mention} 的 {'銀行' if target.lower()=='bank' else '錢包'} 扣除 **${amount}**。")

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
