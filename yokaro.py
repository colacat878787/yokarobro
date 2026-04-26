import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import difflib
from dotenv import load_dotenv

# 載入設定
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# 設定 Bot Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # 需要在 Discord Developer Portal 打開

import logging
from utils import mobile_status # 啟用手機在線模式

# 設定基礎日誌，這樣我們就能看到報錯詳情
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("Yokaro")

class YokaroBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)
        # ... (其餘部分不變)
        self.initial_extensions = [
            'cogs.ai',
            'cogs.security',
            'cogs.music',
            'cogs.webpanel',
            'cogs.voice_ai',
            'cogs.levels',
            'cogs.info',
            'cogs.fun',
            'cogs.twitter',
            'cogs.tts',
            'cogs.updater',
            'cogs.welcome',
            'cogs.record',
            'cogs.economy',
            'cogs.kuji',
            'cogs.admin',
            'cogs.modmail',
            'cogs.tickets',
            'cogs.music_recommend',
            'cogs.management',
            'cogs.system'
        ]

    async def setup_hook(self):
        """載入所有 Cog 分離功能"""
        for ext in self.initial_extensions:
            try:
                print(f"📦 [加載中] 正在喚醒功能: {ext}...")
                await self.load_extension(ext)
                print(f"✅ [成功] {ext} 已經進入工作崗位！")
            except Exception as e:
                print(f"❌ [失敗] {ext} 喚醒過程發生錯誤: {e}")
                import traceback
                traceback.print_exc()
        
        # --- 全域黑名單與追蹤攔截器 ---
        @self.tree.interaction_check
        async def global_interaction_check(interaction: discord.Interaction):
            mgmt = self.get_cog("ManagementCog")
            if mgmt:
                # 1. 攔截黑名單
                if mgmt.is_blacklisted(str(interaction.user.id)):
                    await interaction.response.send_message("❌ 您已被禁止使用洛洛的服務。如有疑問請聯絡開發者。", ephemeral=True)
                    return False
                
                # 2. 追蹤用戶 (Log User)
                mgmt.log_user(interaction.user)
            return True

        # --- [DEBUG] 全域交互錯誤處理監測器 ---
        @self.tree.error
        async def on_tree_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
            logger.error(f"❌ 交互出錯 (來自 {interaction.user}): {error}")
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(f"⚠️ 洛洛偵測到交互內部錯誤：{error}", ephemeral=True)
                except:
                    pass

        # 同步 Slash 指令
        await self.tree.sync()
        print("📁 Slash Commands 同步完成")

    async def on_ready(self):
        print("====================================")
        print(f"🤖 祈星‧優卡洛 (Yokaro) 啟動成功！")
        print(f"👤 登入身分: {self.user.name} (ID: {self.user.id})")
        print(f"🧠 AI 核心: OpenAI GPT 模式")
        print(f"📦 版本狀態: 2026-04-12 深度優化 (延遲修復版)")
        print("====================================")
        
        # 設定簡單的狀態
        activity = discord.Game(name="!help | 嗷嗷嗷～")
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            # 取得用戶輸入的指令名稱
            cmd_name = ctx.invoked_with
            
            # 1. 取得所有本地指令清單 (包含別名)
            all_commands = []
            for cmd in self.commands:
                all_commands.append(cmd.name)
                all_commands.extend(cmd.aliases)
            
            # 2. 尋找最接近的本地指令
            matches = difflib.get_close_matches(cmd_name, all_commands, n=1, cutoff=0.6)
            
            if matches:
                return await ctx.send(f"嗷嗷～洛洛找不到 `!{cmd_name}` 這個指令，你是不是要打 `!{matches[0]}` 呢？")
            
            # 3. 推薦其他機器人的功能 (映射表)
            OTHER_BOTS = {
                'rank': "MEE6", 'levels': "MEE6", 'leaderboard': "MEE6",
                'ban': "Dyno 或 MEE6", 'kick': "Dyno", 'mute': "Dyno", 'warn': "Dyno",
                'p!play': "Pancake", ';;play': "FredBoat",
                '$wa': "Mudae", '$ha': "Mudae",
                'beg': "Dank Memer", 'search': "Dank Memer"
            }
            
            if cmd_name in OTHER_BOTS:
                return await ctx.send(f"嗷～洛洛沒有 `!{cmd_name}` 功能，但這看起來像是 **{OTHER_BOTS[cmd_name]}** 機器人的指令，你可以去呼喚它喔！")
            
            # 4. 真的找不到時的賣萌回應
            try: await ctx.send(f"嗷嗷嗷～洛洛找不到 `!{cmd_name}` 這個指令喔！可以輸入 `!help` 查看洛洛會什麼！")
            except: pass
            return
        
        try:
            if isinstance(error, commands.MissingPermissions):
                await ctx.send("洛洛偵測到你沒有權限執行這個動作喔！嗷～")
            else:
                await ctx.send(f"嗷嗷嗷～發生錯誤了：{error}")
        except:
            print(f"⚠️ [Error Handler Log] 指令錯誤且無法傳回訊息: {error}")

# 機器人實例
bot = YokaroBot()

# --- 基礎全域指令 ---
@bot.hybrid_command(name='ping', aliases=['延遲'])
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def ping(ctx):
    """檢查機器人延遲"""
    await ctx.send(f'🏓 砰！延遲是 {round(bot.latency * 1000)}ms')

@bot.hybrid_command(name='version', aliases=['版本'])
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def version(ctx):
    """查看機器人目前的代碼版本"""
    import subprocess
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode('utf-8').strip()
        await ctx.send(f"🤖 目前 Yokaro 運行的版本是: `{commit}`")
    except:
        await ctx.send("🤖 目前無法取得版本資訊（可能不是透過 Git 啟動的）。")

@bot.command(name='reboot', aliases=['重啟'])
@commands.has_permissions(administrator=True)
async def reboot(ctx):
    """(管理員) 重啟機器人"""
    await ctx.send("⚙️ 洛洛正在重啟中，請稍候一下喔！嗷～")
    exit(0) # 搭配 start.sh 循環實現自動重啟

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 持久化 View 不設 timeout

    @discord.ui.button(label="🛡️ 管理/系統", style=discord.ButtonStyle.primary, custom_id="help_security")
    async def security(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🛡️ 管理與系統指令", description="只有管理員權限才能使用的核心功能", color=0x34495e)
        embed.add_field(name="!setup_verify / !設定驗證", value="設定入群驗證按鈕 (防機器人)", inline=False)
        embed.add_field(name="!welcome_test / !測試歡迎", value="模擬新成員加入的歡迎訊息", inline=False)
        embed.add_field(name="!panel / !後台", value="💡 開啟管理員專用圖形控制面板 (V2)", inline=False)
        embed.add_field(name="!ticket / !開單", value="💡 發送票單啟動儀表板", inline=False)
        embed.add_field(name="!更新紀錄 [set]", value="查看 GitHub 同步紀錄或設定通知頻道", inline=False)
        embed.add_field(name="!reboot / !重啟", value="💡 強制重啟並拉取最新的 GitHub 代碼", inline=False)
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="🎵 語音/音樂", style=discord.ButtonStyle.primary, custom_id="help_music")
    async def music(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🎵 語音頻道與音樂功能", color=0x2ecc71)
        embed.add_field(name="!play / !播放 [歌名]", value="搜尋並播放 Youtube 音樂", inline=True)
        embed.add_field(name="!skip / !跳過", value="跳到下一首", inline=True)
        embed.add_field(name="!stop / !停止", value="清空隊列並離開頻道", inline=True)
        embed.add_field(name="!say / !廣播 [文字]", value="💡 讓洛洛在語音頻道說話 (TTS)", inline=False)
        embed.add_field(name="!m推 / !推歌", value="💡 隨機推薦一首好聽的歌 (含自動整點推送)", inline=False)
        embed.set_footer(text="提示：洛洛也支援多音軌混音播放喔！")
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="🎥 影像/錄影", style=discord.ButtonStyle.danger, custom_id="help_record")
    async def record(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🎥 洛洛錄影機 (影視級系統)", description="業界最強！錄製語音並自動生成「帶字幕與頭像動畫」的影片。", color=0xe74c3c)
        embed.add_field(name="!record start / !錄音 開始", value="進入頻道捕捉語音訊號 (需所有成員同意)", inline=False)
        embed.add_field(name="!record stop / !錄音 停止", value="結束錄製並啟動「AI 自動剪輯與字幕燒製」", inline=False)
        embed.add_field(name="📩 Modmail 客服", value="直接私訊給洛洛即可開啟與管理員的連線", inline=False)
        embed.set_footer(text="錄影完成後，影片會自動傳送到當前文字頻道。嗷嗷嗷～")
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="💰 經濟/遊戲", style=discord.ButtonStyle.success, custom_id="help_economy")
    async def economy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="💰 經濟、一番賞與博弈系統", color=0xf1c40f)
        embed.add_field(name="!balance / !錢包", value="查看自己的現金與銀行存摺", inline=True)
        embed.add_field(name="!ATM / !銀行", value="💡 圖形化 ATM 系統 (存提款)", inline=True)
        embed.add_field(name="!work / !打工", value="賺取洛洛幣，有冷卻時間喔！", inline=True)
        embed.add_field(name="!kuji / !一番賞", value="🎟️ 抽星空主題一番賞 (內含稀有頭銜)", inline=False)
        embed.add_field(name="!gamble / !賭博 [金額]", value="翻倍大挑戰，心臟要夠強！", inline=False)
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="🔍 雜項/資訊", style=discord.ButtonStyle.secondary, custom_id="help_info")
    async def info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🔍 實用工具、等級與運勢", color=0x95a5a6)
        embed.add_field(name="!weather / !天氣 [城市]", value="即時天氣訊號監測", inline=True)
        embed.add_field(name="!stock / !股價 [代號]", value="查詢美股/台股即時報價", inline=True)
        embed.add_field(name="!wiki / !查 [關鍵字]", value="維基百科深度搜尋", inline=True)
        embed.add_field(name="!profile / !等級", value="查看你的等級與 XP 經驗值卡片", inline=True)
        embed.add_field(name="!fortune / !運勢", value="抽一張每日靈感籤詩", inline=True)
        embed.set_footer(text="聊天、升級、跟洛洛互動吧！")
        await interaction.edit_original_response(embed=embed)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        logger.error(f"HelpView Error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ Help 面板發生錯誤: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Help 面板發生錯誤: {error}", ephemeral=True)

@bot.hybrid_command(name='help', aliases=['幫助', '求救'])
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def help(ctx):
    """顯示按鈕導航的功能說明"""
    embed = discord.Embed(
        title="🌟 祈星‧優卡洛 互動指令面板",
        description="洛洛現在支援全新的按鈕選單囉！\n請點擊下方的按鈕來切換不同的指令分類：",
        color=0xffc0cb
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="提示：所有指令皆支援中英雙語通用喔！")
    
    await ctx.send(embed=embed, view=HelpView())

if __name__ == "__main__":
    import subprocess
    print("🛠️ 正在偵測系統套件...")
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ ffmpeg 已準備就緒")
    except:
        print("❌ 找不到 ffmpeg")
        
    if not DISCORD_TOKEN or DISCORD_TOKEN == "YOUR_TOKEN_HERE":
        print("❌ 錯誤: 請在 .env 檔案中設定 DISCORD_TOKEN！")
    else:
        try:
            bot.run(DISCORD_TOKEN)
        except Exception as e:
            print(f"❌ 機器人連線中斷: {e}")
            exit(1)