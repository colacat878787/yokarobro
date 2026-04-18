import discord
from discord.ext import commands
import asyncio
from utils.config import config_manager

class ModmailView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id

    @discord.ui.button(label="❌ 結束對話 (End Session)", style=discord.ButtonStyle.danger, custom_id="end_modmail")
    async def end_session(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.close_session(self.user_id, self.guild_id, interaction.channel)
        await interaction.followup.send("✅ 已結束此會話並通知用戶。")

class ServerSelect(discord.ui.Select):
    def __init__(self, cog, guilds):
        options = [
            discord.SelectOption(label=guild.name, value=str(guild.id), description=f"ID: {guild.id}")
            for guild in guilds
        ]
        super().__init__(placeholder="請選擇你要聯繫的伺服器...", options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        guild_id = int(self.values[0])
        await self.cog.start_session(interaction.user, guild_id, interaction)

class ServerSelectView(discord.ui.View):
    def __init__(self, cog, guilds):
        super().__init__(timeout=60)
        self.add_item(ServerSelect(cog, guilds))

class ModmailCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {} # user_id: guild_id
        self.channel_map = {} # user_id: channel_id

    async def get_or_create_category(self, guild):
        category_name = "📩 | 聯絡洛洛 (Modmail)"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
            }
            category = await guild.create_category(category_name, overwrites=overwrites)
        return category

    async def start_session(self, user, guild_id, interaction=None):
        guild = self.bot.get_guild(guild_id)
        if not guild: return
        
        self.active_sessions[user.id] = guild_id
        category = await self.get_or_create_category(guild)
        
        channel_name = f"mail-{user.name}".replace(" ", "-").lower()
        channel = discord.utils.get(category.text_channels, name=channel_name)
        
        if not channel:
            channel = await guild.create_text_channel(channel_name, category=category)
            embed = discord.Embed(title="📩 新的 Modmail 會話", color=0x3498db)
            embed.add_field(name="用戶", value=f"{user.name} ({user.id})", inline=False)
            embed.set_footer(text="直接在此頻道回覆即可傳送私訊給用戶")
            await channel.send(embed=embed, view=ModmailView(self, user.id, guild_id))
        
        self.channel_map[user.id] = channel.id
        
        msg = f"✅ 已成功連線至 **{guild.name}** 的管理團隊！\n現在你可以直接傳送訊息，我會幫你轉發給管理員喔。嗷嗷嗷～"
        if interaction:
            await interaction.response.edit_message(content=msg, view=None)
        else:
            await user.send(msg)

    async def close_session(self, user_id, guild_id, channel):
        if user_id in self.active_sessions:
            del self.active_sessions[user_id]
        if user_id in self.channel_map:
            del self.channel_map[user_id]
            
        user = self.bot.get_user(user_id)
        if user:
            try:
                await user.send(f"📴 你與伺服器管理員的連線已中斷。如需再次聯絡，請重新傳送私訊！")
            except: pass
        
        # 這裡不刪除頻道，讓管理員決定是否手動刪除或自動過段時間刪除
        await channel.send("🔒 會話已由管理員關閉。")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return

        # 1. 處理私訊 (User -> Staff)
        if isinstance(message.channel, discord.DMChannel):
            if message.author.id in self.active_sessions:
                guild_id = self.active_sessions[message.author.id]
                channel_id = self.channel_map.get(message.author.id)
                channel = self.bot.get_channel(channel_id)
                if channel:
                    embed = discord.Embed(description=message.content, color=0xecf0f1)
                    embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
                    if message.attachments:
                        embed.set_image(url=message.attachments[0].url)
                    await channel.send(embed=embed)
                else:
                    await message.author.send("❌ 找不到對應的對話頻道，連線可能已失效。請稍後再試。")
                    del self.active_sessions[message.author.id]
            else:
                # 找出共享伺服器
                common_guilds = [g for g in self.bot.guilds if g.get_member(message.author.id)]
                if not common_guilds:
                    await message.author.send("嗷～洛洛找不到你跟我在同一個伺服器耶...")
                    return
                
                if len(common_guilds) == 1:
                    await self.start_session(message.author, common_guilds[0].id)
                    # 重新處理這條訊息
                    await self.on_message(message)
                else:
                    embed = discord.Embed(title="📫 聯絡管理團隊", description="洛洛偵測到你位於多個有我的伺服器中，請選擇你想聯絡的對象：", color=0xf1c40f)
                    await message.author.send(embed=embed, view=ServerSelectView(self, common_guilds))

        # 2. 處理 Modmail 頻道訊息 (Staff -> User)
        elif message.channel.name.startswith("mail-"):
            # 找出這頻道屬於哪個用戶 (這部分可以優化為用資料庫存，目前先簡單處理)
            user_id = None
            for uid, cid in self.channel_map.items():
                if cid == message.channel.id:
                    user_id = uid
                    break
            
            if user_id:
                user = self.bot.get_user(user_id)
                if user:
                    embed = discord.Embed(description=message.content, color=0x3498db)
                    embed.set_author(name=f"管理員 ({message.guild.name})", icon_url=message.guild.icon.url if message.guild.icon else None)
                    if message.attachments:
                        embed.set_image(url=message.attachments[0].url)
                    try:
                        await user.send(embed=embed)
                        await message.add_reaction("✅")
                    except:
                        await message.channel.send("❌ 無法傳送私訊給用戶 (用戶可能關閉了私訊功能)")

async def setup(bot):
    await bot.add_cog(ModmailCog(bot))
