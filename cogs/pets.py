import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import asyncio
from datetime import datetime, timedelta
from utils.data_store import pet_store, checkin_store

# 寵物種類
PET_TYPES = {
    "🐱 貓咪": {"emoji": "🐱", "hp": 100, "hunger": 100, "happiness": 100},
    "🐶 狗狗": {"emoji": "🐶", "hp": 120, "hunger": 90, "happiness": 110},
    "🐰 兔子": {"emoji": "🐰", "hp": 60, "hunger": 80, "happiness": 130},
    "🐉 小龍": {"emoji": "🐉", "hp": 150, "hunger": 70, "happiness": 80},
    "🦊 狐狸": {"emoji": "🦊", "hp": 80, "hunger": 85, "happiness": 120},
    "🐧 企鵝": {"emoji": "🐧", "hp": 70, "hunger": 95, "happiness": 100},
}

class PetView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(label="🍖 餵食", style=discord.ButtonStyle.success, custom_id="pet_feed")
    async def feed(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是你的寵物！", ephemeral=True)
            return
        data = pet_store.get(str(self.user_id), {})
        if not data:
            await interaction.response.send_message("你還沒有寵物！用 `!領養` 領養一隻吧！", ephemeral=True)
            return
        data["hunger"] = min(data.get("hunger", 100) + 20, 100)
        data["happiness"] = min(data.get("happiness", 100) + 5, 100)
        data["last_feed"] = datetime.now().isoformat()
        pet_store.set(str(self.user_id), data)
        await interaction.response.send_message(f"🍖 你餵了 {data['name']}，牠很開心！", ephemeral=True)
    
    @discord.ui.button(label="🎾 玩耍", style=discord.ButtonStyle.primary, custom_id="pet_play")
    async def play(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是你的寵物！", ephemeral=True)
            return
        data = pet_store.get(str(self.user_id), {})
        if not data:
            await interaction.response.send_message("你還沒有寵物！用 `!領養` 領養一隻吧！", ephemeral=True)
            return
        data["happiness"] = min(data.get("happiness", 100) + 30, 100)
        data["hunger"] = max(data.get("hunger", 100) - 10, 0)
        pet_store.set(str(self.user_id), data)
        await interaction.response.send_message(f"🎾 你跟 {data['name']} 玩得很開心！", ephemeral=True)
    
    @discord.ui.button(label="💤 休息", style=discord.ButtonStyle.secondary, custom_id="pet_sleep")
    async def sleep(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是你的寵物！", ephemeral=True)
            return
        data = pet_store.get(str(self.user_id), {})
        if not data:
            await interaction.response.send_message("你還沒有寵物！", ephemeral=True)
            return
        data["hp"] = min(data.get("hp", 100) + 20, PET_TYPES[data["pet_type"]]["hp"])
        data["hunger"] = max(data.get("hunger", 100) - 5, 0)
        pet_store.set(str(self.user_id), data)
        await interaction.response.send_message(f"💤 {data['name']} 睡了一覺，恢復了體力！", ephemeral=True)

class PetCog(commands.Cog):
    """🐾 虛擬寵物養成系統"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name='領養')
    async def adopt_pet(self, ctx: commands.Context):
        """領養一隻虛擬寵物"""
        uid = str(ctx.author.id)
        if pet_store.get(uid):
            await ctx.send(f"{ctx.author.mention} 你已經有寵物了！用 `!寵物` 查看")
            return
        
        # 選擇寵物
        embed = discord.Embed(title="🐾 領養寵物", description="選擇你想領養的寵物：", color=discord.Color.blue())
        for pet_name, pet_info in PET_TYPES.items():
            embed.add_field(name=pet_name, value=f"HP:{pet_info['hp']} 飽食:{pet_info['hunger']} 快樂:{pet_info['happiness']}", inline=True)
        
        view = PetSelectView(ctx.author.id)
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name='寵物')
    async def show_pet(self, ctx: commands.Context):
        """查看你的寵物狀態"""
        uid = str(ctx.author.id)
        data = pet_store.get(uid)
        if not data:
            await ctx.send(f"{ctx.author.mention} 你還沒有寵物！用 `!領養` 領養一隻吧！")
            return
        
        embed = discord.Embed(
            title=f"{data['emoji']} {data['name']}",
            description=f"{ctx.author.display_name} 的寵物",
            color=discord.Color.blue()
        )
        embed.add_field(name="❤️ HP", value=f"{'🟩' * (data['hp']//10)}{'⬜' * ((100-data['hp'])//10)} {data['hp']}", inline=False)
        embed.add_field(name="🍖 飽食度", value=f"{'🟫' * (data['hunger']//10)}{'⬜' * ((100-data['hunger'])//10)} {data['hunger']}", inline=False)
        embed.add_field(name="😊 快樂度", value=f"{'🟡' * (data['happiness']//10)}{'⬜' * ((100-data['happiness'])//10)} {data['happiness']}", inline=False)
        
        # 隨機事件：挖到金幣
        if random.random() < 0.3:
            gold = random.randint(5, 30)
            coin_data = checkin_store.get(uid, {"balance": 0})
            coin_data["balance"] = coin_data.get("balance", 0) + gold
            checkin_store.set(uid, coin_data)
            embed.add_field(name="🎁 寵物挖到寶！", value=f"你的寵物挖到了 **{gold}** 金幣！", inline=False)
        
        view = PetView(ctx.author.id)
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name='放生')
    async def release_pet(self, ctx: commands.Context):
        """放生寵物（慎用）"""
        uid = str(ctx.author.id)
        if not pet_store.get(uid):
            await ctx.send("你沒有寵物可以放生...")
            return
        
        confirm_view = ConfirmReleaseView(ctx.author.id)
        await ctx.send("⚠️ 確定要放生你的寵物嗎？這個動作無法撤銷！", view=confirm_view)

class PetSelectView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
    
    @discord.ui.select(placeholder="🐾 選擇寵物...", options=[
        discord.SelectOption(label=name, emoji=info["emoji"], value=name)
        for name, info in PET_TYPES.items()
    ])
    async def select_pet(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是你的選單！", ephemeral=True)
            return
        
        pet_name = select.values[0]
        pet_info = PET_TYPES[pet_name]
        
        # 取名字
        await interaction.response.send_message(f"✍️ 請在聊天框中為你的 {pet_name} 取一個名字（30秒內）：", ephemeral=True)
        
        def check(m):
            return m.author.id == self.user_id and m.channel.id == interaction.channel.id
        
        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=30)
            name = msg.content.strip()[:20]
            await msg.delete()
            
            data = {
                "name": name,
                "pet_type": pet_name,
                "emoji": pet_info["emoji"],
                "hp": pet_info["hp"],
                "hunger": pet_info["hunger"],
                "happiness": pet_info["happiness"],
                "level": 1,
                "exp": 0,
                "created_at": datetime.now().isoformat(),
                "last_feed": datetime.now().isoformat(),
            }
            pet_store.set(str(self.user_id), data)
            
            embed = discord.Embed(
                title=f"🎉 恭喜領養成功！",
                description=f"{pet_info['emoji']} **{name}** ({pet_name}) 成為了你的寵物！\n好好照顧牠吧！",
                color=discord.Color.green()
            )
            await interaction.edit_original_response(embed=embed, view=None)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ 取名超時，請重新領養。", ephemeral=True)

class ConfirmReleaseView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=30)
        self.user_id = user_id
    
    @discord.ui.button(label="✅ 確定放生", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是你的選單！", ephemeral=True)
            return
        pet_store.delete(str(self.user_id))
        await interaction.response.send_message("🥺 你的寵物已放生... 牠會想念你的。")
        await interaction.message.delete()
    
    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        await interaction.response.send_message("✅ 已取消放生。", ephemeral=True)
        await interaction.message.delete()

async def setup(bot: commands.Bot):
    await bot.add_cog(PetCog(bot))