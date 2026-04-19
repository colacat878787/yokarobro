import discord
from discord.ext import commands, tasks
import re
import os
import aiohttp
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

SPAM_KEYWORDS = ["免費代打", "購買加賴", "送外幣", "加 LINE", "抽獎連結"]
URL_REGEX = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

# 惡意連結資料源
BLACKLIST_URLS = [
    "https://raw.githubusercontent.com/nikolais-links/nikolais-links/main/links.json",
    "https://raw.githubusercontent.com/buildtheearth/domain-blacklist/master/domains.txt"
]

class SecurityView(discord.ui.View):
    def __init__(self, role_name):
        super().__init__(timeout=None)
        self.role_name = role_name

    @discord.ui.button(label="✅ 我已閱讀並同意守則", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        role = discord.utils.get(interaction.guild.roles, name=self.role_name)
        if role:
            try:
                await interaction.user.add_roles(role)
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
        self.verify_role = os.getenv("VERIFY_ROLE_NAME", "成員")
        
        # 惡意網域清單 (預設包含 youareanidiot.cc)
        self.malicious_domains = {"youareanidiot.cc", "youareanidiot.org", "youareanidiot.xyz"}
        
        # 啟動自動更新任務
        self.update_blacklist_task.start()
        
        # 註冊持久化視圖
        self.bot.add_view(SecurityView(self.role_name))
        print("💠 洛洛防護盾已啟動，惡意網址資料庫載入中...")

    def cog_unload(self):
        self.update_blacklist_task.cancel()

    @tasks.loop(hours=6.0)
    async def update_blacklist_task(self):
        """定期從開源社群抓取最新惡意網域名稱"""
        async with aiohttp.ClientSession() as session:
            for url in BLACKLIST_URLS:
                try:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            if url.endswith(".json"):
                                data = await resp.json()
                                if isinstance(data, list):
                                    self.malicious_domains.update(data)
                                elif isinstance(data, dict):
                                    # 有些格式是字典包含列表
                                    for key in data:
                                        if isinstance(data[key], list):
                                            self.malicious_domains.update(map(str, data[key]))
                            else:
                                text = await resp.text()
                                # 逐行讀取 txt 格式的網域
                                domains = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
                                self.malicious_domains.update(domains)
                except Exception as e:
                    print(f"⚠️ 無法從 {url} 更新黑名單: {e}")
        print(f"🛡️ 惡意網址庫更新完成，目前監控 {len(self.malicious_domains)} 個網域")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return

        content = message.content.lower()
        
        # 1. 偵測惡意連結
        urls = re.findall(URL_REGEX, content)
        has_malicious = False
        blocked_domain = ""

        if urls:
            for url in urls:
                try:
                    domain = urlparse(url).netloc.lower()
                    # 檢查網域是否在黑名單中 (包含子網域檢查)
                    for mal_domain in self.malicious_domains:
                        if domain == mal_domain or domain.endswith(f".{mal_domain}"):
                            has_malicious = True
                            blocked_domain = domain
                            break
                except: continue
                if has_malicious: break

        # 2. 檢測廣告關鍵字 (管理員依然豁免廣告關鍵字 check)
        is_spam = False
        if not message.author.guild_permissions.administrator:
            is_spam = any(k in content for k in SPAM_KEYWORDS)
        
        # 3. 執行攔截動作
        if has_malicious or is_spam or (not message.author.guild_permissions.administrator and len(urls) > 5):
            # 如果是惡意連結，管理員也要攔截！
            print(f"🚨 [Security] 偵測到惡意網域: {blocked_domain} from {message.author}")
            await message.delete()
            
            if has_malicious:
                # 網址去連結化 (Defang): 把 . 換成 [.] 防止點擊
                defanged_domain = blocked_domain.replace(".", "[.]")
                warning = f"⚠️ **危險連結攔截** ⚠️\n> {message.author.mention} 剛剛發送了疑似惡意或整人的連結 (**{defanged_domain}**)，洛洛已經幫大家把它吃掉啦！請大家保護好自己的帳號喔！🐾"
                await message.channel.send(warning)
                try:
                    await message.author.send(f"❌ 洛洛偵測到你發送了被列為危險的連結：`{blocked_domain}`，為了保護伺服器安全，該訊息已被刪除。")
                except: pass
            
            elif is_spam:
                await message.channel.send(f"⚠️ {message.author.mention} 因發送廣告訊息被自動禁言 1 小時並刪除訊息！")
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
