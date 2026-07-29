import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
from datetime import datetime, timedelta
from utils.data_store import greeting_store, get_today_str

class GreetButton(View):
    """打招呼按鈕 View"""
    def __init__(self, new_member_id: int):
        super().__init__(timeout=None)
        self.new_member_id = new_member_id
        self.greeters = set()
    
    @discord.ui.button(label="👋 打招呼", style=discord.ButtonStyle.primary, custom_id="greet_btn")
    async def greet_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.new_member_id:
            await interaction.response.send_message("你不能對自己打招呼啦！", ephemeral=True)
            return
        
        if interaction.user.id in self.greeters:
            await interaction.response.send_message("你已經打過招呼了喔！👋", ephemeral=True)
            return
        
        self.greeters.add(interaction.user.id)
        
        # 記錄到資料庫
        member_key = str(self.new_member_id)
        today = get_today_str()
        greet_data = greeting_store.get(member_key, {})
        if today not in greet_data:
            greet_data[today] = []
        if interaction.user.id not in greet_data[today]:
            greet_data[today].append(interaction.user.id)
        greeting_store.set(member_key, greet_data)
        
        await interaction.response.send_message(
            f"🎉 {interaction.user.mention} 跟新朋友打了招呼！太暖心了～",
            ephemeral=True
        )
        
        # 更新按鈕人數顯示
        await self.update_button_label(interaction.message)
    
    async def update_button_label(self, message):
        count = len(self.greeters)
        self.children[0].label = f"👋 打招呼 ({count}人)"
        try:
            await message.edit(view=self)
        except:
            pass

class GreetingButtonsCog(commands.Cog):
    """🤝 互動打招呼按鈕系統"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id = None
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """新成員加入時發送含按鈕的歡迎訊息"""
        if not self.welcome_channel_id:
            return
        
        channel = self.bot.get_channel(self.welcome_channel_id)
        if not channel:
            return
        
        view = GreetButton(member.id)
        
        embed = discord.Embed(
            title=f"🎉 歡迎 {member.display_name} 來到伺服器！",
            description=(
                f"{member.mention} 歡迎加入！🎊\n\n"
                f"點擊下方 👋 按鈕跟新朋友打個招呼吧！\n"
                f"24小時後我會統計有多少人跟你打招呼並私訊告訴你唷！"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"加入時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        msg = await channel.send(embed=embed, view=view)
        
        # 啟動24小時後結算計時器
        self.bot.loop.create_task(self.schedule_greeting_summary(member, channel, view, msg))
    
    async def schedule_greeting_summary(self, member, channel, view, msg):
        """24小時後發送結算私訊"""
        try:
            await asyncio.sleep(86400)  # 24小時
        except asyncio.CancelledError:
            return
        
        # 停用按鈕
        view.children[0].disabled = True
        view.children[0].label = f"👋 已截止 ({len(view.greeters)}人)"
        try:
            await msg.edit(view=view)
        except:
            pass
        
        # 發送私訊結算
        count = len(view.greeters)
        try:
            embed = discord.Embed(
                title="📊 24小時打招呼結算",
                description=f"在過去的24小時內，共有 **{count}** 個人跟你打了招呼！",
                color=discord.Color.blue()
            )
            if count > 0:
                greeter_names = []
                for uid in view.greeters:
                    u = channel.guild.get_member(uid)
                    if u:
                        greeter_names.append(u.display_name)
                if greeter_names:
                    embed.add_field(name="👋 打過招呼的人", value="\n".join(greeter_names), inline=False)
                embed.add_field(name="🎉 心得", value="你在這個伺服器並不孤單！多多跟大家互動吧！", inline=False)
            else:
                embed.description = "可惜24小時內沒有人跟你打招呼...🥺 不過別灰心，主動跟大家聊天就會認識朋友了！"
            
            await member.send(embed=embed)
        except:
            pass
    
    @commands.command(name='設定歡迎頻道')
    @commands.has_permissions(administrator=True)
    async def set_welcome_channel(self, ctx: commands.Context):
        """設定新成員歡迎頻道"""
        self.welcome_channel_id = ctx.channel.id
        await ctx.send(f"✅ 已將 {ctx.channel.mention} 設定為新成員歡迎頻道！")
    
    @commands.command(name='打招呼統計')
    async def greeting_stats(self, ctx: commands.Context, member: discord.Member = None):
        """查看打招呼統計"""
        if member is None:
            member = ctx.author
        
        data = greeting_store.get(str(member.id), {})
        if not data:
            await ctx.send(f"{member.mention} 還沒有被打招呼的記錄喔！")
            return
        
        total = sum(len(v) for v in data.values())
        embed = discord.Embed(
            title=f"📊 {member.display_name} 的打招呼統計",
            description=f"總共被 {total} 人次打招呼",
            color=discord.Color.blue()
        )
        
        # 顯示最近7天的記錄
        days = sorted(data.keys(), reverse=True)[:7]
        for day in days:
            count = len(data[day])
            embed.add_field(name=day, value=f"{count} 人", inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(GreetingButtonsCog(bot))