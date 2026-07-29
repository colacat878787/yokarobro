import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import asyncio
from utils.data_store import casino_store, checkin_store

class BlackjackView(View):
    """21點遊戲介面"""
    def __init__(self, user_id: int, bet: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet = bet
        self.player_hand = [self.draw_card(), self.draw_card()]
        self.dealer_hand = [self.draw_card(), self.draw_card()]
        self.game_over = False
    
    def draw_card(self):
        return random.randint(1, 11)
    
    def hand_value(self, hand):
        total = sum(hand)
        aces = hand.count(11)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total
    
    def hand_display(self, hand, hide_first=False):
        if hide_first:
            return f"❓ + {hand[1]}"
        return " + ".join(str(c) for c in hand)
    
    async def update_message(self, interaction):
        embed = discord.Embed(title="🃏 21點 Blackjack", color=discord.Color.blue())
        embed.add_field(name="👤 你的手牌", value=f"`{self.hand_display(self.player_hand)}` = **{self.hand_value(self.player_hand)}**", inline=False)
        embed.add_field(name="🤖 莊家手牌", value=f"`{self.hand_display(self.dealer_hand, not self.game_over)}`", inline=False)
        embed.add_field(name="💰 賭注", value=f"**{self.bet}** 金幣", inline=False)
        
        if self.game_over:
            p_val = self.hand_value(self.player_hand)
            d_val = self.hand_value(self.dealer_hand)
            
            if p_val > 21:
                result = "💥 爆牌！你輸了..."
                color = discord.Color.red()
            elif d_val > 21 or p_val > d_val:
                result = f"🎉 你贏了 {self.bet * 2} 金幣！"
                color = discord.Color.green()
                self.payout()
            elif p_val == d_val:
                result = "🤝 平手！退還賭注"
                color = discord.Color.greyple()
                self.payout(refund=True)
            else:
                result = f"😔 你輸了 {self.bet} 金幣..."
                color = discord.Color.red()
            
            embed.color = color
            embed.add_field(name="📊 結果", value=result, inline=False)
            
            for child in self.children:
                child.disabled = True
        
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except:
            await interaction.edit_original_response(embed=embed, view=self)
    
    def payout(self, refund=False):
        uid = str(self.user_id)
        data = checkin_store.get(uid, {"balance": 0})
        if refund:
            data["balance"] += self.bet
        else:
            data["balance"] += self.bet * 2
        checkin_store.set(uid, data)
    
    @discord.ui.button(label="✅ 要牌", style=discord.ButtonStyle.success)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是你的遊戲！", ephemeral=True)
            return
        self.player_hand.append(self.draw_card())
        if self.hand_value(self.player_hand) >= 21:
            self.game_over = True
        await self.update_message(interaction)
    
    @discord.ui.button(label="🛑 停牌", style=discord.ButtonStyle.danger)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是你的遊戲！", ephemeral=True)
            return
        self.game_over = True
        while self.hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.draw_card())
        await self.update_message(interaction)
    
    async def on_timeout(self):
        self.game_over = True
        for child in self.children:
            child.disabled = True

class CasinoCog(commands.Cog):
    """🎰 虛擬賭場"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name='21點')
    async def blackjack(self, ctx: commands.Context, bet: int = 10):
        """玩21點（下注金幣）"""
        uid = str(ctx.author.id)
        data = checkin_store.get(uid, {"balance": 0})
        
        if data["balance"] < bet:
            await ctx.send(f"{ctx.author.mention} 金幣不足！你只有 {data['balance']} 金幣 💰")
            return
        
        if bet < 10:
            await ctx.send("最低下注 10 金幣！")
            return
        
        data["balance"] -= bet
        checkin_store.set(uid, data)
        
        view = BlackjackView(ctx.author.id, bet)
        embed = discord.Embed(title="🃏 21點 Blackjack", color=discord.Color.blue())
        embed.add_field(name="👤 你的手牌", value=f"`{view.hand_display(view.player_hand)}` = **{view.hand_value(view.player_hand)}**", inline=False)
        embed.add_field(name="🤖 莊家手牌", value=f"`{view.hand_display(view.dealer_hand, True)}`", inline=False)
        embed.add_field(name="💰 賭注", value=f"**{bet}** 金幣", inline=False)
        
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name='骰子')
    async def dice(self, ctx: commands.Context, bet: int = 10):
        """擲骰子比大小"""
        uid = str(ctx.author.id)
        data = checkin_store.get(uid, {"balance": 0})
        
        if data["balance"] < bet:
            await ctx.send(f"{ctx.author.mention} 金幣不足！")
            return
        
        data["balance"] -= bet
        checkin_store.set(uid, data)
        
        player_roll = random.randint(1, 6)
        bot_roll = random.randint(1, 6)
        
        embed = discord.Embed(title="🎲 擲骰子比大小", color=discord.Color.blue())
        embed.add_field(name="👤 你的骰子", value=f"**{player_roll}**", inline=True)
        embed.add_field(name="🤖 電腦的骰子", value=f"**{bot_roll}**", inline=True)
        
        if player_roll > bot_roll:
            win = bet * 2
            data["balance"] += win
            embed.add_field(name="🎉 結果", value=f"你贏了 **{win}** 金幣！", inline=False)
            embed.color = discord.Color.green()
        elif player_roll == bot_roll:
            data["balance"] += bet
            embed.add_field(name="🤝 結果", value="平手！退還賭注", inline=False)
            embed.color = discord.Color.greyple()
        else:
            embed.add_field(name="😔 結果", value=f"你輸了 **{bet}** 金幣...", inline=False)
            embed.color = discord.Color.red()
        
        checkin_store.set(uid, data)
        await ctx.send(embed=embed)
    
    @commands.command(name='猜拳')
    async def rps(self, ctx: commands.Context, choice: str, bet: int = 10):
        """猜拳（石頭/剪刀/布）"""
        uid = str(ctx.author.id)
        data = checkin_store.get(uid, {"balance": 0})
        
        if data["balance"] < bet:
            await ctx.send(f"{ctx.author.mention} 金幣不足！")
            return
        
        choices = {"石頭": "🪨", "剪刀": "✂️", "布": "📄"}
        if choice not in choices:
            await ctx.send("請選擇：石頭、剪刀、布")
            return
        
        data["balance"] -= bet
        checkin_store.set(uid, data)
        
        bot_choice = random.choice(list(choices.keys()))
        player_emoji = choices[choice]
        bot_emoji = choices[bot_choice]
        
        # 判斷勝負
        win_conditions = {"石頭": "剪刀", "剪刀": "布", "布": "石頭"}
        
        embed = discord.Embed(title="✊ 猜拳", color=discord.Color.blue())
        embed.add_field(name="👤 你", value=f"{player_emoji} {choice}", inline=True)
        embed.add_field(name="🤖 電腦", value=f"{bot_emoji} {bot_choice}", inline=True)
        
        if win_conditions[choice] == bot_choice:
            win = bet * 2
            data["balance"] += win
            embed.add_field(name="🎉 結果", value=f"你贏了 **{win}** 金幣！", inline=False)
            embed.color = discord.Color.green()
        elif choice == bot_choice:
            data["balance"] += bet
            embed.add_field(name="🤝 結果", value="平手！退還賭注", inline=False)
            embed.color = discord.Color.greyple()
        else:
            embed.add_field(name="😔 結果", value=f"你輸了 **{bet}** 金幣...", inline=False)
            embed.color = discord.Color.red()
        
        checkin_store.set(uid, data)
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(CasinoCog(bot))