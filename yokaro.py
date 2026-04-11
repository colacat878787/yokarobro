import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

# 載入設定
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# 設定 Bot Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # 需要在 Discord Developer Portal 打開

class YokaroBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)
        self.initial_extensions = [
            'cogs.ai',
            'cogs.security',
            'cogs.music',
            'cogs.levels',
            'cogs.info',
            'cogs.fun',
            'cogs.twitter',
            'cogs.tts',
            'cogs.updater'
        ]

    async def setup_hook(self):
        """載入所有 Cog 分離功能"""
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                print(f"✅ 已載入功能: {ext}")
            except Exception as e:
                print(f"❌ 載入失敗 {ext}: {e}")
        
        # 同步 Slash 指令 (部分 Cog 可能有用到)
        await self.tree.sync()
        print("📁 Slash Commands 同步完成")

    async def on_ready(self):
        print("====================================")
        print(f"🤖 祈星‧優卡洛 (Yokaro) 啟動成功！")
        print(f"👤 登入身分: {self.user.name} (ID: {self.user.id})")
        print(f"🧠 AI 核心: OpenAI GPT 模式")
        print("====================================")
        
        # 設定簡單的狀態
        activity = discord.Game(name="!help | 嗷嗷嗷～")
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("洛洛偵測到你沒有權限執行這個動作喔！嗷～")
        else:
            await ctx.send(f"嗷嗷嗷～發生錯誤了：{error}")

# 機器人實例
bot = YokaroBot()

# --- 基礎全域指令 ---
@bot.command(name='延遲')
async def ping(ctx):
    """檢查機器人延遲"""
    await ctx.send(f'🏓 砰！延遲是 {round(bot.latency * 1000)}ms')

@bot.command(name='重啟')
@commands.has_permissions(administrator=True)
async def reboot(ctx):
    """(管理員) 重啟機器人"""
    await ctx.send("⚙️ 洛洛正在重啟中，請稍候一下喔！嗷～")
    exit(0) # 搭配 start.sh 循環實現自動重啟

@bot.command(name='幫助', aliases=['求救'])
async def help(ctx):
    """顯示詳細的功能說明"""
    embed = discord.Embed(title="🌟 祈星‧優卡洛 指令清單", description="洛洛是你的全能小幫手！", color=0xffc0cb)
    
    embed.add_field(name="🛡️ 安全管理", value="`!設定驗證` 設定入群驗證\n(自動偵測廣告 & 過量連結)", inline=False)
    embed.add_field(name="🎵 音樂播放", value="`!播放 [歌名/網址]` 播放音樂\n`!插歌 [歌名/網址]` 插歌 (管理員)\n`!跳過` 跳過 / `!強制跳過` (管理員)\n`!停止` 停止", inline=False)
    embed.add_field(name="🎮 遊戲與運勢", value="`!運勢` 每日抽籤\n`!拉霸` 拉霸機\n`!抽獎 [秒數] [獎品]` 辦抽獎\n`!等級` 查詢等級 XP", inline=False)
    embed.add_field(name="🔍 資訊查詢", value="`!天氣 [城市]` 查天氣\n`!維基 [關鍵字]` 查維基\n`!股價 [代號]` 查股價", inline=False)
    embed.add_field(name="🐦 Twitter 通知", value="`!追蹤推特 [帳號]` 設定推文通知頻道", inline=False)
    embed.add_field(name="💬 AI 對話 & 實況", value="`!廣播` 設定廣播頻道，或是直接標記聊天", inline=False)
    
    embed.set_footer(text="還有什麼洛洛能幫你的嗎？嗷嗷嗷～")
    await ctx.send(embed=embed)

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