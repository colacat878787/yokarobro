import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncio
import random
from datetime import datetime
from utils.data_store import confession_store

class ConfessionModal(Modal, title="💌 匿名告白"):
    def __init__(self):
        super().__init__()
        self.target = TextInput(
            label="告白對象",
            placeholder="寫下你想告白的人的暱稱或名字...",
            required=True,
            max_length=100,
        )
        self.add_item(self.target)
        
        self.content = TextInput(
            label="你想說的話",
            style=discord.TextStyle.long,
            placeholder="寫下你想說的話...（支援文字、網址、圖片連結）",
            required=True,
            max_length=1000,
        )
        self.add_item(self.content)
        
        self.signature = TextInput(
            label="署名（可選）",
            placeholder="例如：一個暗戀你的人、匿名者",
            required=False,
            max_length=50,
        )
        self.add_item(self.signature)

    async def on_submit(self, interaction: discord.Interaction):
        target = self.target.value.strip()
        content = self.content.value
        signature = self.signature.value.strip() or "匿名者"
        
        confession_id = str(int(datetime.now().timestamp()))
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 儲存紀錄
        confession_store.set(confession_id, {
            "target": target,
            "content": content,
            "signature": signature,
            "author_id": interaction.user.id,
            "time": time_str,
            "likes": 0,
            "liked_by": [],
            "published": True
        })
        
        # 直接發佈在當前頻道
        embed = discord.Embed(
            title="💌 匿名告白牆",
            description=f"**💕 給 {target}：**\n\n{content}",
            color=discord.Color.pink()
        )
        embed.set_footer(text=f"—— {signature} | {time_str}")
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1029/1029183.png")
        
        view = ConfessionView(confession_id, content, signature, time_str, target)
        await interaction.response.send_message(embed=embed, view=view)
        
        # 私訊通知使用者
        try:
            await interaction.user.send(f"💌 你的告白已成功發佈在 {interaction.channel.mention} 頻道！\n**給 {target}：** {content[:50]}...")
        except:
            pass

class ConfessionView(View):
    def __init__(self, confession_id: str, content: str, signature: str, time: str, target: str):
        super().__init__(timeout=None)
        self.confession_id = confession_id
        self.content = content
        self.signature = signature
        self.time = time
        self.target = target
    
    @discord.ui.button(label="💌 我也想知道", style=discord.ButtonStyle.primary, custom_id="confess_like")
    async def like_button(self, interaction: discord.Interaction, button: Button):
        data = confession_store.get(self.confession_id, {})
        liked_by = data.get("liked_by", [])
        
        if interaction.user.id in liked_by:
            await interaction.response.send_message("你已經按過囉！", ephemeral=True)
            return
        
        liked_by.append(interaction.user.id)
        data["likes"] = len(liked_by)
        data["liked_by"] = liked_by
        confession_store.set(self.confession_id, data)
        
        button.label = f"💌 我也想知道 ({data['likes']})"
        await interaction.message.edit(view=self)
        await interaction.response.send_message("你對這則告白產生了共鳴！💕", ephemeral=True)

class ConfessionCog(commands.Cog):
    """🗣️ 匿名告白牆"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name='告白')
    async def confess(self, ctx: commands.Context):
        """發送匿名告白（會跳出填寫視窗）"""
        modal = ConfessionModal()
        await ctx.send("💌 請填寫告白內容：", view=ConfessionTriggerView(modal), ephemeral=True)

class ConfessionTriggerView(View):
    def __init__(self, modal):
        super().__init__(timeout=60)
        self.modal = modal
    
    @discord.ui.button(label="✍️ 寫下告白", style=discord.ButtonStyle.primary)
    async def write_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(self.modal)

async def setup(bot: commands.Bot):
    await bot.add_cog(ConfessionCog(bot))