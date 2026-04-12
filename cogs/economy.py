import discord
from discord.ext import commands
import json
import os
import random
import time
from datetime import datetime, timedelta

ECONOMY_FILE = "economy.json"

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

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_data()
        self.work_cooldowns = {}

    def load_data(self):
        if os.path.exists(ECONOMY_FILE):
            with open(ECONOMY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(ECONOMY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

    def get_user_data(self, user_id):
        if user_id not in self.data:
            self.data[user_id] = {"balance": 0, "last_daily": 0}
        return self.data[user_id]

    def get_balance(self, user_id):
        return self.get_user_data(user_id)["balance"]

    def add_money(self, user_id, amount):
        user_data = self.get_user_data(user_id)
        user_data["balance"] += amount
        self.save_data()

    @commands.command(name='balance', aliases=['錢包', '餘額'])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user_id = str(member.id)
        bal = self.get_balance(user_id)
        
        embed = discord.Embed(title=f"💰 {member.display_name} 的錢包", color=0xf1c40f)
        embed.add_field(name="持有金額", value=f"**${bal}**", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='daily', aliases=['簽到', '每日獎菜'])
    async def daily(self, ctx):
        user_id = str(ctx.author.id)
        user_data = self.get_user_data(user_id)
        
        now = time.time()
        last_daily = user_data.get("last_daily", 0)
        
        if now - last_daily < 86400: # 24小時
            remaining = 86400 - (now - last_daily)
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await ctx.send(f"嗷～你今天領過獎勵了！請再等 **{hours} 小時 {minutes} 分鐘** 喔！")
            return
        
        reward = 500
        user_data["balance"] += reward
        user_data["last_daily"] = now
        self.save_data()
        
        await ctx.send(f"✨ 簽到成功！獲得了每日獎勵 **${reward}**！目前餘額：**${user_data['balance']}**。嗷嗷嗷～")

    @commands.command(name='work', aliases=['工作'])
    async def work(self, ctx):
        user_id = str(ctx.author.id)
        now = time.time()
        
        if user_id in self.work_cooldowns:
            last_work = self.work_cooldowns[user_id]
            if now - last_work < 600: # 10分鐘冷卻
                remaining = 600 - (now - last_work)
                await ctx.send(f"嗷～你剛下班，體力還沒恢復呢！請再等 **{int(remaining // 60)} 分鐘** 喔！")
                return

        self.work_cooldowns[user_id] = now
        view = WorkView(ctx, self)
        await ctx.send("💼 **你要選擇哪種工作呢？** (不同工作報酬不同喔！)", view=view)

    @commands.command(name='rps', aliases=['猜拳'])
    async def rps(self, ctx, choice_str: str, bet: int = 0):
        choices = {"剪刀": "✌️", "石頭": "✊", "布": "✋", "rock": "✊", "paper": "✋", "scissors": "✌️"}
        
        # 標準化輸入
        user_choice = None
        for k, v in choices.items():
            if choice_str.lower() == k:
                user_choice = k if k in ["剪刀", "石頭", "布"] else ("剪刀" if k == "scissors" else ("石頭" if k == "rock" else "布"))
                break
        
        if not user_choice:
            await ctx.send("嗷～請輸入正確的拳型：剪刀、石頭、布！")
            return

        user_id = str(ctx.author.id)
        if bet < 0:
            await ctx.send("嗷～賭金不能是負的啦！")
            return
            
        if bet > self.get_balance(user_id):
            await ctx.send(f"嗷嗷嗷～你的錢不夠支付 **${bet}** 的賭注喔！")
            return

        bot_choices = ["剪刀", "石頭", "布"]
        bot_choice = random.choice(bot_choices)
        
        user_emoji = choices[user_choice]
        bot_emoji = choices[bot_choice]

        embed = discord.Embed(title="🎮 猜拳遊戲", color=0x9b59b6)
        embed.add_field(name="你出了", value=f"{user_emoji} {user_choice}", inline=True)
        embed.add_field(name="洛洛出了", value=f"{bot_emoji} {bot_choice}", inline=True)

        if user_choice == bot_choice:
            result_text = "結果是：**平手**！下次再戰！嗷～"
            embed.color = 0x95a5a6
        elif (user_choice == "石頭" and bot_choice == "剪刀") or \
             (user_choice == "剪刀" and bot_choice == "布") or \
             (user_choice == "布" and bot_choice == "石頭"):
            if bet > 0:
                self.add_money(user_id, bet)
                result_text = f"結果是：**你贏了**！獲得了 **${bet}**！嗷嗷嗷～🎉"
            else:
                result_text = "結果是：**你贏了**！太強啦！嗷嗷嗷～🎉"
            embed.color = 0x2ecc71
        else:
            if bet > 0:
                self.add_money(user_id, -bet)
                result_text = f"結果是：**洛洛贏了**！輸掉了 **${bet}**... 拍拍。嗷嗚..."
            else:
                result_text = "結果是：**洛洛贏了**！手氣不太好喔！嗷嗚..."
            embed.color = 0xe74c3c

        embed.description = result_text
        if bet > 0:
            embed.set_footer(text=f"目前餘額: ${self.get_balance(user_id)}")
            
        await ctx.send(embed=embed)

    @commands.command(name='gamble', aliases=['賭博', '比大小'])
    async def gamble(self, ctx, bet: int):
        user_id = str(ctx.author.id)
        if bet <= 0:
            await ctx.send("嗷～請下注大於 0 的金額！")
            return
            
        if bet > self.get_balance(user_id):
            await ctx.send(f"嗷嗷嗷～你的錢包現在只有 **${self.get_balance(user_id)}**，不夠賭啦！")
            return

        await ctx.send(f"🎲 洛洛擲出了骰子... 結果是...")
        
        # 簡易 50/50 賭博，但稍微偏向莊家一点点（或者完全隨機）
        win = random.random() > 0.52 # 48% 勝率
        
        if win:
            self.add_money(user_id, bet)
            new_bal = self.get_balance(user_id)
            await ctx.send(f"✨ **大獲全勝！** 你贏到了 **${bet}**！目前餘額：**${new_bal}**。嗷嗷嗷～")
        else:
            self.add_money(user_id, -bet)
            new_bal = self.get_balance(user_id)
            await ctx.send(f"💀 **慘敗！** 洛洛拿走了你的 **${bet}**... 目前餘額：**${new_bal}**。嗷嗚...")

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
