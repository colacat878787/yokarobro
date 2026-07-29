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
        content = self.content.value
        signature = self.signature.value.strip() or "匿名者"
        
        # 儲存
        confession_id = str(int(datetime.now().timestamp()))
        confession_store.set(confession_id, {
            "content": content,
            "signature": signature,
            "author_id": interaction.user.id,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "likes": 0,
            "liked_by": []
        })
        
        await interaction.response.send_message(
            "✅ 你的告白已送出！等待審核後就會發佈到頻道中～ 💌",
            ephemeral=True
        )

class ConfessionView(View):
    def __init__(self, confession_id: str, content: str, signature: str, time: str):
        super().__init__(timeout=None)
        self.confession_id = confession_id
        self.content = content
        self.signature = signature
        self.time = time
    
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
        self.channel_id = None
    
    @commands.command(name='告白')
    async def confess(self, ctx: commands.Context):
        """發送匿名告白（會跳出填寫視窗）"""
        modal = ConfessionModal()
        await ctx.send("💌 請填寫告白內容：", view=ConfessionTriggerView(modal), ephemeral=True)
    
    @commands.command(name='設定告白頻道')
    @commands.has_permissions(administrator=True)
    async def set_confession_channel(self, ctx: commands.Context):
        """設定告白牆發佈頻道"""
        self.channel_id = ctx.channel.id
        await ctx.send(f"✅ 已將 {ctx.channel.mention} 設定為告白牆發佈頻道！")
    
    @commands.command(name='審核告白')
    @commands.has_permissions(administrator=True)
    async def review_confessions(self, ctx: commands.Context):
        """審核待發佈的告白"""
        all_data = confession_store.get_all()
        pending = {k: v for k, v in all_data.items() if not v.get("published", False)}
        
        if not pending:
            await ctx.send("目前沒有待審核的告白。")
            return
        
        for cid, data in list(pending.items())[:5]:  # 一次顯示5則
            embed = discord.Embed(
                title="💌 匿名告白（待審核）",
                description=data["content"],
                color=discord.Color.pink()
            )
            embed.set_footer(text=f"署名：{data['signature']} | {data['time']}")
            
            view = ReviewView(cid, self)
            await ctx.send(embed=embed, view=view)
    
    async def publish_confession(self, confession_id: str):
        """發佈告白到頻道"""
        if not self.channel_id:
            return
        
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return
        
        data = confession_store.get(confession_id)
        if not data:
            return
        
        data["published"] = True
        confession_store.set(confession_id, data)
        
        embed = discord.Embed(
            title="💌 匿名告白牆",
            description=data["content"],
            color=discord.Color.pink()
        )
        embed.set_footer(text=f"—— {data['signature']} | {data['time']}")
        
        view = ConfessionView(confession_id, data["content"], data["signature"], data["time"])
        await channel.send(embed=embed, view=view)

class ConfessionTriggerView(View):
    def __init__(self, modal):
        super().__init__(timeout=60)
        self.modal = modal
    
    @discord.ui.button(label="✍️ 寫下告白", style=discord.ButtonStyle.primary)
    async def write_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(self.modal)

class ReviewView(View):
    def __init__(self, confession_id: str, cog: ConfessionCog):
        super().__init__(timeout=60)
        self.confession_id = confession_id
        self.cog = cog
    
    @discord.ui.button(label="✅ 發佈", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: Button):
        await self.cog.publish_confession(self.confession_id)
        await interaction.message.delete()
        await interaction.response.send_message("✅ 已發佈告白！", ephemeral=True)
    
    @discord.ui.button(label="❌ 拒絕", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: Button):
        confession_store.delete(self.confession_id)
        await interaction.message.delete()
        await interaction.response.send_message("已拒絕該告白。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ConfessionCog(bot))