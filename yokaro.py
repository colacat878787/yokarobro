import discord
from discord.ext import commands
from discord import app_commands
import os
import sys
import asyncio
import difflib
import importlib
import subprocess
import aiohttp
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

# 載入設定
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# 設定 Bot Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # 需要在 Discord Developer Portal 打開
intents.presences = True # 必須開啟才能看到遊戲狀態！

import logging
from utils import mobile_status # 啟用手機在線模式

# 設定基礎日誌，這樣我們就能看到報錯詳情
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("Yokaro")

class StatusServerHandler(BaseHTTPRequestHandler):
    """處理 Pi 的狀態查詢請求"""
    
    def do_GET(self):
        if self.path == "/status":
            status = {
                "status": "ok",
                "bot_name": bot.user.name if bot.user else "starting",
                "guilds": len(bot.guilds) if bot.guilds else 0,
                "latency": round(bot.latency * 1000) if bot.latency else None,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status, ensure_ascii=False).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # 靜默 HTTP 日誌

class YokaroBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)
        # Track deleted roles for restore functionality
        self.deleted_roles = {}  # {guild_id: [list of deleted role data]}
        # Status cycling
        self.status_messages = [
            (discord.Status.online, "でも　そんなんじゃ　だめ"),
            (discord.Status.online, "もう　そんなんじゃ　ほら"),
            (discord.Status.online, "心は進化するよ"),
            (discord.Status.online, "もっと　もっと"),
        ]
        self.status_index = 0
        self.music_mode = False
        self.status_task = None
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
            'cogs.system',
            'cogs.music_web',
            'cogs.otaku',
            'cogs.games',
            'cogs.werewolf',
            'cogs.widget',
            'cogs.mcstatus',
            'cogs.reloader',
            'cogs.delete_log',
            'cogs.test_system',        # 🔍 系統測試工具
            # ===== 新功能模組 =====
            'cogs.greeting_buttons',   # 🤝 互動打招呼按鈕
            'cogs.checkin_cards',      # 🎮 每日簽到+抽卡
            'cogs.confession',         # 🗣️ 匿名告白牆
            'cogs.stocks',             # 📈 股票市場系統
            'cogs.alien',              # 👽 外星文翻譯機
            'cogs.backup',             # 💾 伺服器備份系統
            'cogs.screenshot',         # 📸 網頁截圖功能
            'cogs.oauth',              # 🔐 OAuth 加入伺服器系統
            'cogs.server_settings',    # ⚙️ 伺服器功能開關面板
            'cogs.hug',                # 🐾 抱抱功能
            'cogs.menu',               # 🎯 互動式選單
            'cogs.context_menus',      # 📱 右鍵選單功能
            'cogs.httpcat',            # 🐱 HTTP Cat 狀態碼圖片
            'cogs.timed_role',         # ⏰ 限時身分組
            'cogs.ytsubcountdown',     # 📊 YouTube 訂閱數倒數計時
            'cogs.language',           # 🌐 多語言切換系統
            'cogs.anime',              # 🎬 動漫搜索 (Jikan/MyAnimeList)
                        'cogs.server_counter',     # 📊 伺服器計數器
            # ===== 热门机器人功能完补 =====
            'cogs.reaction_roles',     # 🎭 反應角色系統
            'cogs.afk',                # 💤 AFK 離開系統
            'cogs.reminder',           # ⏰ 提醒/鬧鐘系統
            'cogs.starboard',          # ⭐ 星板系統
            'cogs.auto_role',          # 🤖 自動身分組系統
            'cogs.alarm',              # ⏰ 鬧鐘系統
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
            # 超級用戶權限繞過 (1113353915010920452)
            if str(interaction.user.id) == "1113353915010920452":
                return True
            
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
        ai_mode = "本地模式 (Ollama)"
        if os.getenv("GEMINI_API_KEY"): ai_mode = "Google Gemini 模式"
        elif os.getenv("OPENAI_API_KEY"): ai_mode = "OpenAI GPT 模式"
        
        print("====================================")
        print(f"🤖 幽芙優 (小幽) / Yokaro 啟動成功！")
        print(f"👤 登入身分: {self.user.name} (ID: {self.user.id})")
        print(f"🧠 AI 核心: {ai_mode}")
        print(f"📦 版本狀態: 2026-07-31 全面改版 (幽芙優)")
        
        # 備援系統：啟動狀態查詢伺服器
        main_server_url = os.getenv("MAIN_SERVER_URL")
        if main_server_url:
            # 啟動狀態查詢伺服器（讓 Pi 可以檢查主伺服器狀態）
            status_thread = threading.Thread(target=self._run_status_server, daemon=True)
            status_thread.start()
            print(f"🍓 備援系統: 狀態查詢伺服器已啟動")
            print(f"   Pi 可透過 {main_server_url}/status 檢查狀態")
        else:
            print("🍓 備援系統: 未設定 MAIN_SERVER_URL，Pi 無法檢查主伺服器狀態")
        
        print("====================================")
        
        # 立即設定第一個輪播狀態（不使用等待，直接設定）
        try:
            status, message = self.status_messages[0]
            activity = discord.Activity(
                type=discord.ActivityType.playing,
                name=message
            )
            await self.change_presence(status=status, activity=activity)
            print(f"✅ 初始狀態已設定: {status} - {message}")
        except Exception as e:
            print(f"⚠️ 設定初始狀態失敗: {e}")
        
        # 啟動狀態輪播任務
        if not self.status_task or self.status_task.done():
            self.status_task = self.loop.create_task(self._status_cycler())
            print("✅ 狀態輪播任務已啟動")
        else:
            print("⚠️ 狀態輪播任務已在運行中")
    
    async def _status_cycler(self):
        """背景任務：輪播狀態訊息"""
        await self.wait_until_ready()
        print("🔄 狀態輪播任務開始運行")
        
        status_list = [
            (discord.Status.online, "でも　そんなんじゃ　だめ"),
            (discord.Status.online, "もう　そんなんじゃ　ほら"),
            (discord.Status.online, "心は進化するよ"),
            (discord.Status.online, "もっと　もっと"),
        ]
        
        status_idx = 0  # 從第一個開始輪播
        
        while not self.is_closed():
            try:
                if not self.music_mode:
                    status, message = status_list[status_idx]
                    print(f"📊 更新狀態: {status} - {message}")
                    activity = discord.Activity(
                        type=discord.ActivityType.playing,
                        name=message
                    )
                    await self.change_presence(status=status, activity=activity)
                    status_idx = (status_idx + 1) % len(status_list)
                else:
                    print("🎵 音樂模式中，跳過狀態輪播")
                
                # 每 10 秒切換一次
                await asyncio.sleep(10)
            except Exception as e:
                print(f"⚠️ 狀態輪播錯誤: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(10)
        
        print("🛑 狀態輪播任務已停止")
    
    async def _update_status(self):
        """更新狀態（音樂模式或一般模式）"""
        if self.music_mode:
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name="🎧 戴上耳機享受音樂中..."
            )
            await self.change_presence(status=discord.Status.online, activity=activity)
        # 否則由 _status_cycler 處理
    
    def set_music_mode(self, enabled: bool):
        """切換音樂模式"""
        self.music_mode = enabled
        if enabled:
            # 音樂模式啟動時立即更新狀態
            self.loop.create_task(self._update_status())
    
    def _run_status_server(self):
        """啟動狀態查詢伺服器（背景執行緒）"""
        try:
            server = HTTPServer(("0.0.0.0", 8080), StatusServerHandler)
            print("🍓 狀態查詢伺服器運行在埠 8080")
            server.serve_forever()
        except Exception as e:
            print(f"⚠️ 狀態查詢伺服器啟動失敗: {e}")

    # 已移除心跳發送功能，改為 Pi 主動輪詢
    
    async def on_command_error(self, ctx, error):
        # 超級用戶權限繞過 (1113353915010920452)
        if str(ctx.author.id) == "1113353915010920452":
            if isinstance(error, commands.MissingPermissions):
                # 超級用戶跳過權限檢查，繼續執行指令
                return
        
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
    from utils.i18n import t
    gid = ctx.guild.id if ctx.guild else None
    await ctx.send(t(gid, "ping.latency", ms=round(bot.latency * 1000)))

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
        embed.add_field(name="!webpanel", value="🔐 **黑科技：生成 TryCloudflare 遠端管理後台**", inline=False)
        embed.add_field(name="!ticket / !開單", value="💡 發送票單啟動儀表板", inline=False)
        embed.add_field(name="!更新紀錄 [set] / !更新速遞 [set]", value="查看 GitHub 同步紀錄或設定通知頻道", inline=False)
        embed.add_field(name="!reboot / !重啟", value="💡 強制重啟並拉取最新的 GitHub 代碼", inline=False)
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="🎵 語音/音樂", style=discord.ButtonStyle.primary, custom_id="help_music")
    async def music(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🎵 語音頻道與音樂功能", color=0x2ecc71)
        embed.add_field(name="!play / !播放 [歌名]", value="搜尋並播放 Youtube/Spotify 音樂", inline=True)
        embed.add_field(name="!recap / !回顧", value="📊 查看您的音樂 DNA 排行榜", inline=True)
        embed.add_field(name="!antirickroll [on/off]", value="🛡️ **反 Rickroll 護盾：拒絕惡作劇**", inline=False)
        embed.add_field(name="!ducking / !247", value="🐥 自動降音量 / 🌌 永不打烊模式", inline=False)
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

    @discord.ui.button(label="💰 經濟/股票", style=discord.ButtonStyle.success, custom_id="help_economy")
    async def economy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="💰 經濟、股票與博弈系統", color=0xf1c40f)
        embed.add_field(name="!balance / !錢包", value="查看自己的現金與銀行存摺", inline=True)
        embed.add_field(name="!ATM / !銀行", value="💡 圖形化 ATM 系統 (存提款)", inline=True)
        embed.add_field(name="!work / !打工", value="賺取洛洛幣，有冷卻時間喔！", inline=True)
        embed.add_field(name="!簽到", value="📅 每日簽到獲得金幣 + 連續簽到獎勵，還能抽隨機卡片！", inline=False)
        embed.add_field(name="!抽卡 [數量]", value="🎴 花10金幣抽一張卡，稀有度從普通到神話都有！", inline=False)
        embed.add_field(name="!我的卡片 / !卡片背包", value="📦 查看你擁有的所有卡片收藏", inline=False)
        embed.add_field(name="!kuji / !一番賞", value="🎟️ 抽星空主題一番賞 (內含稀有頭銜)", inline=False)
        embed.add_field(name="!gamble / !賭博 [金額]", value="翻倍大挑戰，心臟要夠強！", inline=False)
        embed.add_field(name="!辦卡 / !信用額度 / !還款", value="💳 Yokaro 黑金信用卡（先買後付）", inline=False)
        embed.add_field(name="📈 股票系統", value="`!股市` 開啟互動面板（行情、買賣、持股、查詢，即時更新）\n`!創股票 [名稱] [股數] [股價]` 創建股票\n`!股票頻道` 設定股票資訊頻道\n`!除牌 [代號]` 下市股票", inline=False)
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="🔍 雜項/告白", style=discord.ButtonStyle.secondary, custom_id="help_info")
    async def info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🔍 實用工具、等級與告白", color=0x95a5a6)
        embed.add_field(name="!weather / !天氣 [城市]", value="即時天氣訊號監測", inline=True)
        embed.add_field(name="!stock / !股價 [代號]", value="查詢美股/台股即時報價", inline=True)
        embed.add_field(name="!wiki / !查 [關鍵字]", value="維基百科深度搜尋", inline=True)
        embed.add_field(name="!profile / !等級", value="查看你的等級與 XP 經驗值卡片", inline=True)
        embed.add_field(name="!fortune / !運勢", value="抽一張每日靈感籤詩", inline=True)
        embed.add_field(name="!告白", value="💌 匿名告白（免審核，直接發在當前頻道）", inline=False)
        embed.add_field(name="!抱抱 / !hug", value="🐾 伸出可愛的小爪爪抱抱你", inline=True)
        embed.add_field(name="!httpcat [狀態碼]", value="🐱 顯示 HTTP 狀態碼的可愛貓咪圖片", inline=True)
        embed.add_field(name="!選單 / !menu", value="🎯 開啟互動式功能選單面板", inline=False)
        embed.add_field(name="右鍵選單功能", value="📱 訊息右鍵選單：\n• 移植 - 複製訊息內容\n• 鼓掌 - 給作者鼓勵\n• 引用 - 引用訊息", inline=False)
        embed.add_field(name="🎭 反應角色 / !rr", value="用戶點擊反應自動獲取身分組", inline=True)
        embed.add_field(name="💤 AFK / !afk", value="設定離開狀態，@你時自動回覆", inline=True)
        embed.add_field(name="⏰ 提醒 / !remindme", value="設定定時提醒，到時間自動通知", inline=True)
        embed.add_field(name="⭐ 星板 / !starboard", value="自動轉發熱門訊息到指定頻道", inline=True)
        embed.add_field(name="🤖 自動身分組 / !autorole", value="新成員加入時自動分配身分組", inline=True)
        embed.set_footer(text="聊天、升級、跟洛洛互動吧！")
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="🎮 小遊戲/娛樂", style=discord.ButtonStyle.success, custom_id="help_games")
    async def games(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🎮 小遊戲與娛樂", color=0x9b59b6)
        embed.add_field(name="!狼人殺 / !werewolf", value="多人語音狼人殺遊戲", inline=True)
        embed.add_field(name="!運勢 / !fortune", value="每日隨機籤詩", inline=True)
        embed.add_field(name="!拉霸 / !slot", value="試手氣拉霸機", inline=True)
        embed.add_field(name="!抽獎 / !giveaway", value="主辦抽獎活動", inline=True)
        embed.add_field(name="!一番賞 / !kuji", value="星空主題抽獎", inline=True)
        embed.add_field(name="!賭博 / !gamble", value="心臟要夠強的翻倍賭博", inline=False)
        embed.set_footer(text="玩遊戲、贏取獎品、讓洛洛陪你玩！")
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

def ensure_packages(packages):
    import importlib.util
    import subprocess
    import sys
    to_install = []
    for pkg in packages:
        if importlib.util.find_spec(pkg) is None:
            to_install.append(pkg)
    if to_install:
        print(f"📦 正在安裝缺少套件: {', '.join(to_install)}")
        subprocess.run([sys.executable, '-m', 'pip', 'install', *to_install], check=False)

if __name__ == "__main__":
    import subprocess
    print("🛠️ 正在偵測系統套件...")
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ ffmpeg 已準備就緒")
    except:
        print("❌ 找不到 ffmpeg")
        
    # Ensure required Python packages are installed before bot startup.
    ensure_packages(['lyricsgenius'])

    if not DISCORD_TOKEN or DISCORD_TOKEN == "YOUR_TOKEN_HERE":
        print("❌ 錯誤: 請在 .env 檔案中設定 DISCORD_TOKEN！")
    else:
        try:
            bot.run(DISCORD_TOKEN)
        except Exception as e:
            print(f"❌ 機器人連線中斷: {e}")
            exit(1)