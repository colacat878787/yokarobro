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
import threading
from datetime import datetime
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
        self.help_view = None
        # ... (其餘部分不變)
        self.initial_extensions = [
            'cogs.user_settings',
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
            'cogs.logging',             # 📋 機器人 Log 系統
        ]
        self.core_cogs = {
            "SecurityCog", "WebPanelCog", "ManagementCog", "SystemCog",
            "MusicWebPanelCog", "UpdaterCog", "ReloaderCog", "DeleteLogCog",
            "TestSystemCog", "AdminCog", "ServerSettingsCog"
        }

    async def setup_hook(self):
        """載入所有 Cog 分離功能"""
        print("[Loader] starting extensions")
        for ext in self.initial_extensions:
            try:
                print(f"📦 [加載中] 正在喚醒功能: {ext}...")
                await self.load_extension(ext)
                print(f"✅ [成功] {ext} 已經進入工作崗位！")
            except Exception as e:
                print(f"❌ [失敗] {ext} 喚醒過程發生錯誤: {e}")
                import traceback
                traceback.print_exc()

            user_settings_command = self.get_command("使用者設定")
            print(
                "[Loader] cogs.user_settings: "
                f"Cog={'OK' if self.get_cog('UserSettingsCog') else 'NONE'}, "
                f"command={'OK' if user_settings_command else 'NONE'}"
            )
        
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
        self._refresh_help_view()

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

    def _refresh_help_view(self):
        self.help_view = FeatureMenuView(self)
    
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

class FeatureMenuView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    def _loaded_modules(self):
        items = []
        for ext in self.bot.initial_extensions:
            cog_name = ext.split(".")[-1].lower()
            cog = self.bot.get_cog(f"{cog_name.capitalize()}Cog")
            if cog:
                items.append((cog.__class__.__name__, ext))
        return items

    def _build_embed(self, title, description, entries):
        embed = discord.Embed(title=title, description=description, color=0x111827)
        for name, value in entries:
            embed.add_field(name=name, value=value, inline=False)
        return embed

    @discord.ui.button(label="🧩 已載入模組", style=discord.ButtonStyle.primary, custom_id="feature_menu_loaded")
    async def loaded(self, interaction: discord.Interaction, button: discord.ui.Button):
        entries = []
        for cog_name, loaded_cog in self.bot.cogs.items():
            commands_list = []
            for cmd in loaded_cog.get_commands():
                if cmd.hidden:
                    continue
                display = f"/{cmd.qualified_name}"
                commands_list.append(display)
            if commands_list:
                entries.append((cog_name, "\n".join(commands_list[:12])))
        embed = self._build_embed("🧩 已載入模組", "只列出目前開機已載入的功能，help 會隨實際模組更新。", entries or [("目前沒有已載入模組", "請確認 cog 是否成功載入")])
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🧭 功能分類", style=discord.ButtonStyle.success, custom_id="feature_menu_groups")
    async def groups(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🧭 功能分類",
            description="按鈕是入口，指令仍保留給熟手和自動化腳本。",
            color=0x0f766e,
        )
        embed.add_field(name="管理 / 系統", value="`!sys`、`!manage`、`!後台`、`!webpanel`", inline=False)
        embed.add_field(name="內容 / 互動", value="`!menu`、`!選單`、`!hug`、`!afk`、`!remindme`", inline=False)
        embed.add_field(name="金流 / 經營", value="`!balance`、`!work`、`!stock`、`!casino`、`!finance`", inline=False)
        embed.add_field(name="AI / 助手", value="`!玩`、`!set_ai`、`!ai`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="⚙️ 管理入口", style=discord.ButtonStyle.danger, custom_id="feature_menu_admin")
    async def admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚙️ 管理入口",
            description="這裡只放正式管理功能，不再塞一堆分散的舊說明。",
            color=0x991b1b,
        )
        embed.add_field(name="系統維運", value="`!sys check` `!sys repair` `!reloadcog`", inline=False)
        embed.add_field(name="伺服器控制", value="`!用戶面板` `!功能列表` `!後台` `!webpanel`", inline=False)
        embed.add_field(name="AI 代理", value="`!ai agent` 可在授權範圍內執行管理動作", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.hybrid_command(name='help', aliases=['幫助', '求救'])
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def help(ctx):
    """顯示動態功能總覽"""
    embed = discord.Embed(
        title="Yokaro 功能總覽",
        description="只會顯示目前已載入的模組與入口，避免 help 變成雜訊清單。",
        color=0x111827
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    loaded = [f"• {name}" for name in bot.cogs.keys()]
    embed.add_field(name="已載入模組", value="\n".join(loaded) or "目前尚未載入模組", inline=False)
    embed.add_field(name="入口指令", value="`!功能表` `!help` `!menu` `!選單`", inline=False)
    embed.set_footer(text="help 會在每次開機後依實際載入模組更新")

    await ctx.send(embed=embed, view=bot.help_view or FeatureMenuView(bot))

@bot.hybrid_command(name='功能表', aliases=['fmenu'])
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def feature_menu(ctx):
    """正式功能表入口"""
    embed = discord.Embed(
        title="功能表",
        description="使用按鈕選功能，指令保留給習慣文字輸入的使用者。",
        color=0x111827,
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await ctx.send(embed=embed, view=bot.help_view or FeatureMenuView(bot))

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
