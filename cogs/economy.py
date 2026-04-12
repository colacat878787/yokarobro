import discord
from discord.ext import commands
import json
import os
import random
import time
import hashlib
from datetime import datetime, timedelta

ECONOMY_FILE = "economy.json"

# --- ATM UI 組件 ---

class ATMModal(discord.ui.Modal):
    def __init__(self, action, economy_cog, target_user_id=None):
        title = "ATM 操作"
        if action == "register": title = "💳 銀行開戶"
        elif action == "login": title = "🔑 銀行登入"
        elif action == "deposit": title = "💰 存款服務"
        elif action == "withdraw": title = "💸 提款服務"
        super().__init__(title=title)
        
        self.action = action
        self.economy_cog = economy_cog
        self.target_user_id = target_user_id

        if action in ["register", "login"]:
            self.password_input = discord.ui.TextInput(
                label="請輸入 4-6 位數密碼",
                placeholder="例如: 1234",
                min_length=4,
                max_length=6,
                style=discord.TextStyle.short
            )
            self.add_item(self.password_input)
        
        if action in ["deposit", "withdraw"]:
            self.amount_input = discord.ui.TextInput(
                label="請輸入金額",
                placeholder="要操作多少錢呢？",
                style=discord.TextStyle.short
            )
            self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user_data = self.economy_cog.get_user_data(user_id)

        if self.action == "register":
            pwd = self.password_input.value
            user_data["password"] = hashlib.sha256(pwd.encode()).hexdigest()
            self.economy_cog.save_data()
            await interaction.response.send_message(f"✅ 開戶完成！密碼已設定。以後請使用密碼登入 ATM 喔！", ephemeral=True)

        elif self.action == "login":
            pwd = self.password_input.value
            hashed_pwd = hashlib.sha256(pwd.encode()).hexdigest()
            if user_data.get("password") == hashed_pwd:
                view = ATMView(interaction.user, self.economy_cog, is_logged_in=True)
                await interaction.response.edit_message(content="🔓 **登入成功！** 請選擇您要進行的金融服務：", view=view)
            else:
                await interaction.response.send_message("❌ 密碼錯誤！請重新嘗試。嗷嗚...", ephemeral=True)

        elif self.action == "deposit":
            try:
                amt = int(self.amount_input.value)
                if amt <= 0: raise ValueError
                if user_data["balance"] < amt:
                    await interaction.response.send_message(f"❌ 錢包餘額不足！你手中只有 **${user_data['balance']}**。", ephemeral=True)
                    return
                
                user_data["balance"] -= amt
                user_data["bank"] = user_data.get("bank", 0) + amt
                self.economy_cog.save_data()
                
                view = ATMView(interaction.user, self.economy_cog, is_logged_in=True)
                await interaction.response.edit_message(content=f"✅ 成功存入 **${amt}** 到銀行！\n目前銀行餘額：**${user_data['bank']}**", view=view)
            except ValueError:
                await interaction.response.send_message("❌ 請輸入有效的數字金額！", ephemeral=True)

        elif self.action == "withdraw":
            try:
                amt = int(self.amount_input.value)
                if amt <= 0: raise ValueError
                bank_bal = user_data.get("bank", 0)
                if bank_bal < amt:
                    await interaction.response.send_message(f"❌ 銀行存款不足！帳戶內只有 **${bank_bal}**。", ephemeral=True)
                    return
                
                user_data["bank"] -= amt
                user_data["balance"] += amt
                self.economy_cog.save_data()
                
                view = ATMView(interaction.user, self.economy_cog, is_logged_in=True)
                await interaction.response.edit_message(content=f"✅ 成功從銀行提取 **${amt}**！\n目前錢包餘額：**${user_data['balance']}**", view=view)
            except ValueError:
                await interaction.response.send_message("❌ 請輸入有效的數字金額！", ephemeral=True)

class ATMView(discord.ui.View):
    def __init__(self, owner, economy_cog, is_logged_in=False):
        super().__init__(timeout=60)
        self.owner = owner
        self.economy_cog = economy_cog
        self.is_logged_in = is_logged_in
        self.update_buttons()

    def update_buttons(self):
        user_id = str(self.owner.id)
        user_data = self.economy_cog.get_user_data(user_id)
        has_account = "password" in user_data

        self.clear_items()
        
        if not self.is_logged_in:
            if not has_account:
                btn_reg = discord.ui.Button(label="🏦 立即開戶", style=discord.ButtonStyle.success)
                btn_reg.callback = self.register_callback
                self.add_item(btn_reg)
            else:
                btn_login = discord.ui.Button(label="🔑 登入銀行", style=discord.ButtonStyle.primary)
                btn_login.callback = self.login_callback
                self.add_item(btn_login)
        else:
            btn_dep = discord.ui.Button(label="💰 存錢", style=discord.ButtonStyle.secondary)
            btn_dep.callback = self.deposit_callback
            self.add_item(btn_dep)
            
            btn_with = discord.ui.Button(label="💸 提款", style=discord.ButtonStyle.danger)
            btn_with.callback = self.withdraw_callback
            self.add_item(btn_with)

            btn_info = discord.ui.Button(label="📄 餘額查詢", style=discord.ButtonStyle.gray)
            btn_info.callback = self.info_callback
            self.add_item(btn_info)

    async def register_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ATMModal("register", self.economy_cog))

    async def login_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ATMModal("login", self.economy_cog))

    async def deposit_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ATMModal("deposit", self.economy_cog))

    async def withdraw_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ATMModal("withdraw", self.economy_cog))

    async def info_callback(self, interaction: discord.Interaction):
        user_data = self.economy_cog.get_user_data(str(self.owner.id))
        embed = discord.Embed(title="🏦 銀行餘額快報", color=0x3498db)
        embed.add_field(name="🏛️ 銀行存款", value=f"**${user_data.get('bank', 0)}**", inline=True)
        embed.add_field(name="👛 錢包現金", value=f"**${user_data['balance']}**", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ ATM 發生錯誤: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ ATM 發生錯誤: {error}", ephemeral=True)

class WorkView(discord.ui.View):
    def __init__(self, ctx, economy_cog):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.economy_cog = economy_cog

    @discord.ui.button(label="去挖礦 ⛏️", style=discord.ButtonStyle.primary)
    async def mine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_work(interaction, "挖礦", 100, 300)

    @discord.ui.button(label="去打工 🍔", style=discord.ButtonStyle.success)
    async def burger(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_work(interaction, "在漢堡店打工", 50, 200)

    @discord.ui.button(label="去寫程式 💻", style=discord.ButtonStyle.secondary)
    async def code(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_work(interaction, "寫程式", 150, 450)

    async def process_work(self, interaction, job_name, min_pay, max_pay):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("這不是你的工作邀請喔！嗷～", ephemeral=True)
            return

        pay = random.randint(min_pay, max_pay)
        self.economy_cog.add_money(str(interaction.user.id), pay)
        
        embed = discord.Embed(title="💼 工作成果", color=discord.Color.green())
        embed.description = f"你剛剛去 **{job_name}**，賺到了 **${pay}**！\n太棒了，繼續加油喔！嗷嗷嗷～"
        embed.set_footer(text=f"目前餘額: ${self.economy_cog.get_balance(str(interaction.user.id))}")
        
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ 工作系統發生錯誤: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ 工作系統發生錯誤: {error}", ephemeral=True)

# --- Economy Cog ---

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_data()
        self.work_cooldowns = {}

    def load_data(self):
        if os.path.exists(ECONOMY_FILE):
            try:
                with open(ECONOMY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: return {}
        return {}

    def save_data(self):
        with open(ECONOMY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

    def get_user_data(self, user_id):
        if user_id not in self.data:
            self.data[user_id] = {"balance": 0, "bank": 0, "last_daily": 0}
        return self.data[user_id]

    def get_balance(self, user_id):
        return self.get_user_data(user_id)["balance"]

    def add_money(self, user_id, amount, to_bank=False):
        user_data = self.get_user_data(user_id)
        if to_bank:
            user_data["bank"] = user_data.get("bank", 0) + amount
        else:
            user_data["balance"] += amount
        self.save_data()

    @commands.command(name='balance', aliases=['錢包', '餘額'])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user_id = str(member.id)
        user_data = self.get_user_data(user_id)
        
        embed = discord.Embed(title=f"💰 {member.display_name} 的資產總覽", color=0xf1c40f)
        embed.add_field(name="👛 錢包現金", value=f"**${user_data['balance']}**", inline=True)
        embed.add_field(name="🏦 銀行存款", value=f"**${user_data.get('bank', 0)}**", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='ATM', aliases=['銀行'])
    async def atm(self, ctx):
        """啟動 ATM 選單功能"""
        user_id = str(ctx.author.id)
        user_data = self.get_user_data(user_id)
        
        embed = discord.Embed(title="🏪 Yokaro 24h 自動櫃員機", description="歡迎使用洛洛銀行服務！請選擇下方的按鈕進行操作。", color=0x2ecc71)
        embed.set_footer(text="洛洛銀行，關心您的每一分錢 🐾")
        
        view = ATMView(ctx.author, self)
        await ctx.send(embed=embed, view=view)

    @commands.command(name='daily', aliases=['簽到'])
    async def daily(self, ctx):
        user_id = str(ctx.author.id)
        user_data = self.get_user_data(user_id)
        now = time.time()
        last_daily = user_data.get("last_daily", 0)
        
        if now - last_daily < 86400:
            remaining = 86400 - (now - last_daily)
            hours, minutes = int(remaining // 3600), int((remaining % 3600) // 60)
            await ctx.send(f"嗷～請再等 **{hours} 小時 {minutes} 分鐘** 喔！")
            return
        
        reward = 500
        user_data["balance"] += reward
        user_data["last_daily"] = now
        self.save_data()
        await ctx.send(f"✨ 簽到成功！獲得了 **${reward}**！目前錢包：**${user_data['balance']}**。")

    @commands.command(name='work', aliases=['工作'])
    async def work(self, ctx):
        user_id = str(ctx.author.id)
        now = time.time()
        if user_id in self.work_cooldowns and now - self.work_cooldowns[user_id] < 600:
            await ctx.send(f"嗷～體力還沒恢復呢！請再等 **{int((600 - (now - self.work_cooldowns[user_id])) // 60)} 分鐘**。")
            return
        self.work_cooldowns[user_id] = now
        await ctx.send("💼 **你要選擇哪種工作呢？**", view=WorkView(ctx, self))

    @commands.command(name='rps', aliases=['猜拳'])
    async def rps(self, ctx, choice_str: str, bet: int = 0):
        choices = {"剪刀": "✌️", "石頭": "✊", "布": "✋", "rock": "✊", "paper": "✋", "scissors": "✌️"}
        user_choice = None
        for k, v in choices.items():
            if choice_str.lower() == k:
                user_choice = k if k in ["剪刀", "石頭", "布"] else ("剪刀" if k == "scissors" else ("石頭" if k == "rock" else "布"))
                break
        if not user_choice:
            await ctx.send("嗷～請輸入正確的拳型：剪刀、石頭、布！")
            return
        user_id = str(ctx.author.id)
        if bet < 0 or bet > self.get_balance(user_id):
            await ctx.send("嗷嗷嗷～賭注金額有誤喔！")
            return
        bot_choice = random.choice(["剪刀", "石頭", "布"])
        user_emoji, bot_emoji = choices[user_choice], choices[bot_choice]
        embed = discord.Embed(title="🎮 猜拳遊戲", color=0x9b59b6)
        embed.add_field(name="你/洛洛", value=f"{user_emoji} vs {bot_emoji}")
        if user_choice == bot_choice:
            embed.description = "結果是：**平手**！"
        elif (user_choice == "石頭" and bot_choice == "剪刀") or (user_choice == "剪刀" and bot_choice == "布") or (user_choice == "布" and bot_choice == "石頭"):
            self.add_money(user_id, bet)
            embed.description = f"結果是：**你贏了**！獲得了 **${bet}**！"
            embed.color = 0x2ecc71
        else:
            self.add_money(user_id, -bet)
            embed.description = f"結果是：**洛洛贏了**！輸掉了 **${bet}**。"
            embed.color = 0xe74c3c
        await ctx.send(embed=embed)

    @commands.command(name='gamble', aliases=['賭博'])
    async def gamble(self, ctx, bet: int):
        user_id = str(ctx.author.id)
        if bet <= 0 or bet > self.get_balance(user_id):
            await ctx.send("嗷～賭注金額有問題喔！")
            return
        win = random.random() > 0.52
        if win:
            self.add_money(user_id, bet)
            await ctx.send(f"✨ **大獲全勝！** 你贏到了 **${bet}**！目前餘額：**${self.get_balance(user_id)}**。")
        else:
            self.add_money(user_id, -bet)
            await ctx.send(f"💀 **慘敗！** 洛洛拿走了你的 **${bet}**... 目前餘額：**${self.get_balance(user_id)}**。")

    # --- 管理員專屬指令 ---

    @commands.command(name='查帳', aliases=['check_account'])
    @commands.has_permissions(administrator=True)
    async def check_account(self, ctx, member: discord.Member):
        """(管理員) 查看特定用戶的財務狀況"""
        user_data = self.get_user_data(str(member.id))
        embed = discord.Embed(title=f"🕵️ 財務調查: {member.display_name}", color=0x34495e)
        embed.add_field(name="Wallet", value=f"${user_data['balance']}")
        embed.add_field(name="Bank", value=f"${user_data.get('bank', 0)}")
        embed.add_field(name="Password Hash", value=f"`{user_data.get('password', '未開戶')[:10]}...`")
        await ctx.send(embed=embed)

    @commands.command(name='撥款', aliases=['add_money_admin'])
    @commands.has_permissions(administrator=True)
    async def add_money_admin(self, ctx, member: discord.Member, amount: int, target="wallet"):
        """(管理員) 強制撥款"""
        is_bank = target.lower() == "bank"
        self.add_money(str(member.id), amount, to_bank=is_bank)
        await ctx.send(f"✅ 已成功為 {member.mention} 的 {'銀行' if is_bank else '錢包'} 注入 **${amount}**！")

    @commands.command(name='扣款', aliases=['remove_money_admin'])
    @commands.has_permissions(administrator=True)
    async def remove_money_admin(self, ctx, member: discord.Member, amount: int, target="wallet"):
        """(管理員) 強制扣款"""
        is_bank = target.lower() == "bank"
        self.add_money(str(member.id), -amount, to_bank=is_bank)
        await ctx.send(f"💸 已強制從 {member.mention} 的 {'銀行' if is_bank else '錢包'} 扣除 **${amount}**。")

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
