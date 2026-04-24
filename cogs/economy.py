import discord
from discord.ext import commands
from discord import app_commands
import json, os, random, time, hashlib, asyncio

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
    def __init__(self, user=None, economy_cog=None):
        super().__init__(timeout=None)
        self.user = user
        self.economy_cog = economy_cog

    @discord.ui.button(label="🏦 立即開戶", style=discord.ButtonStyle.success, custom_id="econ_atm_reg_init")
    async def register_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PasswordModal(self.economy_cog, "register"))

    @discord.ui.button(label="🔑 登入銀行", style=discord.ButtonStyle.primary, custom_id="econ_atm_login_init")
    async def login_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PasswordModal(self.economy_cog, "login"))

class ATMLoggedInView(discord.ui.View):
    def __init__(self, user, economy_cog):
        super().__init__(timeout=None)
        self.user = user
        self.economy_cog = economy_cog

    @discord.ui.button(label="💰 存錢", style=discord.ButtonStyle.secondary, custom_id="econ_atm_deposit")
    async def deposit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AmountModal(self.economy_cog, self.user, "deposit"))

    @discord.ui.button(label="💸 提款", style=discord.ButtonStyle.danger, custom_id="econ_atm_withdraw")
    async def withdraw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AmountModal(self.economy_cog, self.user, "withdraw"))

    @discord.ui.button(label="📄 查餘額", style=discord.ButtonStyle.primary, custom_id="econ_atm_check")
    async def check(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        data = self.economy_cog.get_user_data(str(self.user.id))
        embed = discord.Embed(title="📄 帳戶資訊", color=0x3498db)
        embed.add_field(name="👛 錢包", value=f"${data['balance']}", inline=True)
        embed.add_field(name="🏦 銀行", value=f"${data.get('bank', 0)}", inline=True)
        await interaction.edit_original_response(content=None, embed=embed)

    @discord.ui.button(label="🔴 結束服務/退卡", style=discord.ButtonStyle.secondary, custom_id="econ_atm_logout")
    async def logout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🏦 **洛洛銀行 — 已登出，歡迎下次光臨！🐾**", embed=None, view=None)
        self.stop()

# ──────────────────────────────────────────
#  Work & Mini-game View
# ──────────────────────────────────────────
class LeafGameView(discord.ui.View):
    def __init__(self, user, economy_cog):
        super().__init__(timeout=75)
        self.user = user
        self.economy_cog = economy_cog
        self.score = 0
        self.time_left = 60
        self.leaf_pos = random.randint(0, 24)
        self.ended = False
        
        for i in range(25):
            btn = discord.ui.Button(label="\u200b", style=discord.ButtonStyle.secondary, custom_id=f"leaf_{i}", row=i // 5)
            if i == self.leaf_pos:
                btn.label = "🍃"
                btn.style = discord.ButtonStyle.success
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    def make_callback(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id or self.ended: return
            if idx == self.leaf_pos:
                self.score += 1
                old_pos = self.leaf_pos
                while self.leaf_pos == old_pos:
                    self.leaf_pos = random.randint(0, 24)
                for i, item in enumerate(self.children):
                    if i == old_pos:
                        item.label = "\u200b"
                        item.style = discord.ButtonStyle.secondary
                    if i == self.leaf_pos:
                        item.label = "🍃"
                        item.style = discord.ButtonStyle.success
                await interaction.response.edit_message(embed=self.make_embed(), view=self)
            else:
                await interaction.response.defer()
        return callback

    def make_embed(self):
        embed = discord.Embed(title="🧹 洛洛清道夫大進擊 (5x5)", color=0x27ae60)
        embed.description = f"把葉子 🍃 通通掃掉！\n妳還有 **{self.time_left}** 秒可以努力！"
        embed.add_field(name="✨ 目前分數", value=f"**{self.score}** 片葉子")
        return embed

    async def start_timer(self, msg):
        while self.time_left > 0:
            await asyncio.sleep(10) # 降低更新頻率
            if self.ended: break
            self.time_left -= 10
            try:
                # 檢查訊息是否還在
                await msg.edit(embed=self.make_embed())
            except: 
                break
        
        if not self.ended:
            await self.end_game(msg)

    async def end_game(self, msg):
        self.ended = True
        self.stop()
        
        # 工資平衡：基礎 200 + 分數 * 20
        final_pay = self.score * 20 + random.randint(150, 350)
        self.economy_cog.add_money(str(self.user.id), final_pay)
        
        end_embed = discord.Embed(title="🏁 工作結束！辛苦了！", color=0xf1c40f)
        end_embed.description = (
            f"大總裁在 60 秒內掃了 **{self.score}** 片葉子！\n"
            f"這是您應得的報酬：**${final_pay}**\n"
            f"目前的錢包餘額已經更新囉！🐾"
        )
        try:
            await msg.edit(content="✅ 工作完成！", embed=end_embed, view=None)
        except:
            # 如果編輯失敗，試著發新訊息
            try:
                await msg.channel.send(f"🏁 {self.user.mention} 工作結束！獲得 **${final_pay}**！")
            except: pass

class WorkView(discord.ui.View):
    def __init__(self, user, economy_cog):
        super().__init__(timeout=30)
        self.user = user
        self.economy_cog = economy_cog


    @discord.ui.button(label="🧹 掃葉子 (小遊戲)", style=discord.ButtonStyle.success, custom_id="econ_work_leaf")
    async def leaf_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ 你沒被邀請去掃葉子喔！", ephemeral=True)
        game_view = LeafGameView(self.user, self.economy_cog)
        await interaction.response.edit_message(content=None, embed=game_view.make_embed(), view=game_view)
        msg = await interaction.original_response()
        # 非同步執行計時器，不阻塞按鈕回調
        asyncio.create_task(game_view.start_timer(msg))

    @discord.ui.button(label="⛏️ 去挖礦", style=discord.ButtonStyle.primary, custom_id="econ_work_mine")
    async def mine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._work(interaction, "挖礦", 100, 300)

    @discord.ui.button(label="🍔 去打工", style=discord.ButtonStyle.secondary, custom_id="econ_work_burger")
    async def burger(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._work(interaction, "在漢堡店打工", 50, 200)

    async def _work(self, interaction: discord.Interaction, job: str, mn: int, mx: int):
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
        await interaction.edit_original_response(content=None, embed=embed, view=None)
        self.stop()

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

    @commands.hybrid_command(name='balance', aliases=['錢包', '餘額'])
    async def balance(self, ctx, member: discord.Member = None):
        m = member or ctx.author
        d = self.get_user_data(str(m.id))
        embed = discord.Embed(title=f"💰 {m.display_name} 的資產", color=0xf1c40f)
        embed.add_field(name="👛 錢包", value=f"**${d['balance']}**", inline=True)
        embed.add_field(name="🏦 銀行", value=f"**${d.get('bank',0)}**", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='ATM', aliases=['銀行'])
    async def atm(self, ctx):
        embed = discord.Embed(title="🏪 Yokaro 24h 自動櫃員機", description="歡迎使用洛洛銀行！請點選下方按鈕。", color=0x2ecc71)
        await ctx.send(embed=embed, view=ATMMainView(ctx.author, self))

    @commands.hybrid_command(name='daily', aliases=['簽到'])
    async def daily(self, ctx):
        uid = str(ctx.author.id)
        d = self.get_user_data(uid)
        now = time.time()
        if now - d.get("last_daily", 0) < 86400:
            rem = 86400 - (now - d["last_daily"])
            await ctx.send(f"嗷～請再等 **{int(rem//3600)} 小時** 喔！")
            return
        d["balance"] += 500
        d["last_daily"] = now
        self.save_data()
        await ctx.send(f"✨ 簽到成功！獲得 **$500**！")

    @commands.hybrid_command(name='work', aliases=['工作'])
    async def work(self, ctx):
        uid = str(ctx.author.id)
        now = time.time()
        if uid in self.work_cd and now - self.work_cd[uid] < 600:
            await ctx.send("嗷～休息一下再工作吧！")
            return
        self.work_cd[uid] = now
        await ctx.send("💼 **選擇你要做的工作：**", view=WorkView(ctx.author, self))

    # ────── 管理員專用指令 ──────
    @commands.command(name='更改餘額', aliases=['set_balance', 'modify_money'])
    @commands.has_permissions(administrator=True)
    async def change_balance_admin(self, ctx, member: discord.Member, amount_str: str):
        """
        手動調整使用者錢包餘額。
        !更改餘額 @使用者 +100 (增加)
        !更改餘額 @使用者 -50 (減少)
        !更改餘額 @使用者 500 (直接設定)
        """
        uid = str(member.id)
        data = self.get_user_data(uid)
        
        try:
            if amount_str.startswith('+'):
                diff = int(amount_str[1:])
                data["balance"] += diff
                action_text = f"增加了 ${diff}"
            elif amount_str.startswith('-'):
                diff = int(amount_str[1:])
                data["balance"] -= diff
                action_text = f"扣除了 ${diff}"
            else:
                new_bal = int(amount_str)
                data["balance"] = new_bal
                action_text = f"直接設定為 ${new_bal}"
            
            self.save_data()
            embed = discord.Embed(title="⚙️ 餘額手動調整", color=0x3498db)
            embed.description = f"管理員 {ctx.author.mention} 修改了 {member.mention} 的錢包！"
            embed.add_field(name="異動內容", value=action_text, inline=False)
            embed.add_field(name="目前錢包餘額", value=f"${data['balance']}", inline=False)
            await ctx.send(embed=embed)
            
        except ValueError:
            await ctx.send("嗷～格式不對！請輸入數字或帶有 +/- 的數字。")

    @commands.command(name='撥款')
    @commands.has_permissions(administrator=True)
    async def add_money_admin(self, ctx, member: discord.Member, amount: int, target="wallet"):
        self.add_money(str(member.id), amount, bank=(target.lower()=="bank"))
        await ctx.send(f"✅ 已為 {member.mention} 注入 **${amount}**！")

    @commands.command(name='扣款')
    @commands.has_permissions(administrator=True)
    async def remove_money_admin(self, ctx, member: discord.Member, amount: int, target="wallet"):
        self.add_money(str(member.id), -amount, bank=(target.lower()=="bank"))
        await ctx.send(f"💸 已從 {member.mention} 扣除 **${amount}**。")

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
