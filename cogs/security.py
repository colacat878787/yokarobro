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
# 邀請連結偵測 (支援 discord.gg, discord.com/invite, discordapp.com/invite)
INVITE_REGEX = r'(?:https?://)?(?:www\.)?(?:discord\.gg/|discord(?:app)?\.com/invite/)([a-zA-Z0-9\-]{2,32})'

# 惡意連結與惡意伺服器資料源
BLACKLIST_URLS = [
    "https://raw.githubusercontent.com/nikolais-links/nikolais-links/main/links.json",
    "https://raw.githubusercontent.com/buildtheearth/domain-blacklist/master/domains.txt"
]
BLACKLIST_GUILDS_URL = "https://raw.githubusercontent.com/buildtheearth/domain-blacklist/master/guilds.txt"

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
        
        # 惡意網域與惡意群組 ID 清單
        self.malicious_domains = {"youareanidiot.cc", "youareanidiot.org", "youareanidiot.xyz"}
        self.malicious_guilds = set()
        
        # 邀請連結快取 (防止頻繁請求 API)
        self.invite_cache = {} # code -> (is_malicious, guild_id)
        
        # 啟動自動更新任務
        self.update_blacklist_task.start()
        
        # 註冊持久化視圖
        self.bot.add_view(SecurityView(self.role_name))
        print("💠 洛洛護衛盾已啟動，惡意網址與群組資料庫同步中...")

    def cog_unload(self):
        self.update_blacklist_task.cancel()

    @tasks.loop(hours=6.0)
    async def update_blacklist_task(self):
        """定期從開源社群抓取最新惡意網域與惡意伺服器 ID"""
        async with aiohttp.ClientSession() as session:
            # 1. 更新網域黑名單
            for url in BLACKLIST_URLS:
                try:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            if url.endswith(".json"):
                                data = await resp.json()
                                if isinstance(data, list): self.malicious_domains.update(data)
                                elif isinstance(data, dict):
                                    for k in data:
                                        if isinstance(data[k], list): self.malicious_domains.update(map(str, data[k]))
                            else:
                                text = await resp.text()
                                domains = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
                                self.malicious_domains.update(domains)
                except Exception as e: print(f"⚠️ 無法更新網域黑名單: {e}")

            # 2. 更新伺服器 ID 黑名單
            try:
                async with session.get(BLACKLIST_GUILDS_URL, timeout=10) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        ids = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
                        self.malicious_guilds.update(ids)
            except Exception as e: print(f"⚠️ 無法更新伺服器黑名單: {e}")

        print(f"🛡️ 護衛庫更新完成: {len(self.malicious_domains)} 網域, {len(self.malicious_guilds)} 惡意群組")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return

        content = message.content.lower()
        has_malicious = False
        reason = ""

        # 1. 偵測惡意連結
        urls = re.findall(URL_REGEX, content)
        if urls:
            for url in urls:
                try:
                    domain = urlparse(url).netloc.lower()
                    for mal_domain in self.malicious_domains:
                        if domain == mal_domain or domain.endswith(f".{mal_domain}"):
                            has_malicious = True
                            reason = "惡意網址"
                            break
                except: continue
                if has_malicious: break

        # 2. 偵測惡意伺服器邀請
        invites = re.findall(INVITE_REGEX, content)
        if invites and not has_malicious:
            for code in invites:
                target_id = ""
                is_mal = False
                
                # 檢查快取
                if code in self.invite_cache:
                    is_mal, target_id = self.invite_cache[code]
                else:
                    try:
                        # 呼叫 API 查詢邀請資訊
                        invite = await self.bot.fetch_invite(code)
                        if invite.guild:
                            target_id = str(invite.guild.id)
                            is_mal = target_id in self.malicious_guilds
                        self.invite_cache[code] = (is_mal, target_id)
                    except: continue # 邀請無效或已過期
                
                if is_mal:
                    has_malicious = True
                    reason = "惡意群組邀請"
                    break

        # 3. 檢測廣告關鍵字 (管理員豁免)
        is_spam = False
        if not message.author.guild_permissions.administrator:
            is_spam = any(k in content for k in SPAM_KEYWORDS)
        
        # 4. 執行攔截動作
        if has_malicious or is_spam or (not message.author.guild_permissions.administrator and len(urls) > 5):
            print(f"🚨 [Security] 攔截成功: {reason if has_malicious else 'Spam'} from {message.author}")
            await message.delete()
            
            if has_malicious:
                warning = f"⚠️ **危險內容攔截** ⚠️\n> {message.author.mention} 剛剛發送了疑似惡意或整人的連結，洛洛已經幫大家把它吃掉啦！請大家保護好自己的帳號喔！🐾"
                await message.channel.send(warning)
                try: await message.author.send(f"❌ 洛洛偵測到你發送了危險的內容 ({reason})，為了保護伺服器安全，該訊息已被刪除。")
                except: pass
            
            elif is_spam:
                await message.channel.send(f"⚠️ {message.author.mention} 因發送廣告訊息被自動禁言 1 小時並刪除訊息！")
                try: await message.author.timeout(discord.utils.utcnow() + discord.utils.datetime.timedelta(hours=1))
                except: pass

    @commands.command(name='setup_verify', aliases=['設定驗證'])
    @commands.has_permissions(administrator=True)
    async def setup_verify(self, ctx):
        embed = discord.Embed(title="📜 入群驗證", description="點擊下方按鈕以獲取身分組並加入對話！", color=0x27ae60)
        await ctx.send(embed=embed, view=SecurityView(self.verify_role))

async def setup(bot):
    await bot.add_cog(SecurityCog(bot))
