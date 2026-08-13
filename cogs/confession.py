import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncio
import random
from datetime import datetime
from utils.i18n import t, get_language
from utils.data_store import confession_store

class ConfessionModal(Modal):
    def __init__(self, guild_id=None):
        super().__init__(title=t(guild_id, "confession.modal.title"))
        self._gid = guild_id
        self.target = TextInput(
            label=t(guild_id, "confession.target_label"),
            placeholder=t(guild_id, "confession.target_ph"),
            required=True,
            max_length=100,
        )
        self.add_item(self.target)
        
        self.content = TextInput(
            label=t(guild_id, "confession.content_label"),
            style=discord.TextStyle.long,
            placeholder=t(guild_id, "confession.content_ph"),
            required=True,
            max_length=1000,
        )
        self.add_item(self.content)
        
        self.signature = TextInput(
            label=t(guild_id, "confession.sig_label"),
            placeholder=t(guild_id, "confession.sig_ph"),
            required=False,
            max_length=50,
        )
        self.add_item(self.signature)

    async def on_submit(self, interaction: discord.Interaction):
        gid = self._gid
        target = self.target.value.strip()
        content = self.content.value
        signature = self.signature.value.strip() or t(gid, "confession.anon")
        
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
            title=t(gid, "confession.wall"),
            description=t(gid, "confession.give", target=target, content=content),
            color=discord.Color.pink()
        )
        embed.set_footer(text=f"—— {signature} | {time_str}")
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1029/1029183.png")
        
        view = ConfessionView(confession_id, content, signature, time_str, target)
        await interaction.response.send_message(embed=embed, view=view)
        
        # 私訊通知使用者
        try:
            ch = interaction.channel.mention if interaction.channel else "?"
            await interaction.user.send(
                t(gid, "confession.published", channel=ch, target=target, content=content[:50])
            )
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
        self.guild_id = None
    
    @discord.ui.button(label="💌 我也想知道", style=discord.ButtonStyle.primary, custom_id="confess_like")
    async def like_button(self, interaction: discord.Interaction, button: Button):
        gid = interaction.guild.id if interaction.guild else None
        if self.guild_id is None:
            self.guild_id = gid
        data = confession_store.get(self.confession_id, {})
        liked_by = data.get("liked_by", [])
        
        if interaction.user.id in liked_by:
            await interaction.response.send_message(t(gid, "confession.already"), ephemeral=True)
            return
        
        liked_by.append(interaction.user.id)
        data["likes"] = len(liked_by)
        data["liked_by"] = liked_by
        confession_store.set(self.confession_id, data)
        
        button.label = f"💌 {t(gid, 'confession.like')} ({data['likes']})"
        await interaction.message.edit(view=self)
        await interaction.response.send_message(t(gid, "confession.like_done"), ephemeral=True)

class ConfessionCog(commands.Cog):
    """🗣️ 匿名告白牆"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name='告白')
    async def confess(self, ctx: commands.Context):
        """發送匿名告白（會跳出填寫視窗）"""
        gid = ctx.guild.id if ctx.guild else None
        modal = ConfessionModal(gid)
        await ctx.send(t(gid, "confession.send_prompt"), view=ConfessionTriggerView(modal), ephemeral=True)

class ConfessionTriggerView(View):
    def __init__(self, modal):
        super().__init__(timeout=60)
        self.modal = modal
    
    @discord.ui.button(label="✍️ 寫下告白", style=discord.ButtonStyle.primary)
    async def write_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(self.modal)

async def setup(bot: commands.Bot):
    await bot.add_cog(ConfessionCog(bot))