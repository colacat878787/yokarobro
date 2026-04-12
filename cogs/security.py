import discord
from discord.ext import commands
import re
import os
from dotenv import load_dotenv

load_dotenv()

SPAM_KEYWORDS = ["免費代打", "購買加賴", "送外幣", "加 LINE", "抽獎連結"]
URL_REGEX = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

class SecurityView(discord.ui.View):
    def __init__(self, role_name):
        super().__init__(timeout=None)
        self.role_name = role_name

    @discord.ui.button(label="✅ 我已閱讀並同意守則", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. 立即告知 Discord 我收到了，正在處理中 (思考模式)
        await interaction.response.defer(ephemeral=True)
        
        # 2. 執行邏輯
        role = discord.utils.get(interaction.guild.roles, name=self.role_name)
        if role:
            try:
                await interaction.user.add_roles(role)
                # 3. 處理完成後，修改原本那則「思考中」的內容
                await interaction.edit_original_response(content="✅ 驗證完成！歡迎加入星辰大合唱！嗷嗷嗷～")
            except discord.Forbidden:
                await interaction.edit_original_response(content="❌ 矮油！洛洛權限不夠，請聯絡管理員檢查身分組順序！")
            except Exception as e:
                await interaction.edit_original_response(content=f"❌ 發生未知錯誤：{e}")
        else:
            await interaction.edit_original_response(content=f"嗷～找不到身分組 `{self.role_name}`，請通知管理員！")

class SecurityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_name = "星辰大合唱"
        # 註冊持久化視圖
        self.bot.add_view(SecurityView(self.role_name))
        print("💠 持久化身分驗證按鈕註冊完成")
        self.verify_role = os.getenv("VERIFY_ROLE_NAME", "成員")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        if message.author.guild_permissions.administrator: return

        # 檢測廣告關鍵字
        content = message.content.lower()
        is_spam = any(k in content for k in SPAM_KEYWORDS)
        
        # 檢測過多連結 (防洗版)
        urls = re.findall(URL_REGEX, content)
        if len(urls) > 3 or is_spam:
            await message.delete()
            try:
                await message.author.send("洛洛偵測到你發送廣告或過多連結，訊息已被刪除。請遵守群規喔！")
            except: pass
            
            # 若包含廣告關鍵字，則禁言 1 小時 (需伺服器有禁言權限)
            if is_spam:
                await message.channel.send(f"⚠️ {message.author.mention} 因發送廣告訊息被自動禁言並刪除！")
                # 這裡可以使用 timeout 功能 (Discord API v10)
                try: 
                    await message.author.timeout(discord.utils.utcnow() + discord.utils.datetime.timedelta(hours=1))
                except: pass

    @commands.command(name='setup_verify', aliases=['設定驗證'])
    @commands.has_permissions(administrator=True)
    async def setup_verify(self, ctx):
        embed = discord.Embed(title="📜 入群驗證", description="點擊下方按鈕以獲取身分組並加入對話！", color=0x27ae60)
        await ctx.send(embed=embed, view=SecurityView(self.verify_role))

async def setup(bot):
    await bot.add_cog(SecurityCog(bot))
