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
            'cogs.updater',
            'cogs.welcome',
            'cogs.economy',
            'cogs.kuji',
            'cogs.admin'
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
@bot.command(name='ping', aliases=['延遲'])
async def ping(ctx):
    """檢查機器人延遲"""
    await ctx.send(f'🏓 砰！延遲是 {round(bot.latency * 1000)}ms')

@bot.command(name='version', aliases=['版本'])
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
        super().__init__(timeout=60)

    @discord.ui.button(label="🛡️ 管理/安全", style=discord.ButtonStyle.primary)
    async def security(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🛡️ 管理與安全指令", color=0x3498db)
        embed.add_field(name="!setup_verify / !設定驗證", value="設定入群驗證按鈕", inline=False)
        embed.add_field(name="!panel / !後台", value="💡 管理員專用控制面板", inline=False)
        embed.add_field(name="!reboot / !重啟", value="💡 重啟機器人", inline=False)
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="🎵 音樂/廣播", style=discord.ButtonStyle.primary)
    async def music(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🎵 音樂與廣播指令", color=0x2ecc71)
        embed.add_field(name="!play / !播放", value="播放 Youtube 音樂", inline=True)
        embed.add_field(name="!skip / !跳過", value="下一首", inline=True)
        embed.add_field(name="!stop / !停止", value="下班離開", inline=True)
        embed.add_field(name="!say / !廣播", value="TTS 語音廣播", inline=False)
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="💰 經濟/一番賞", style=discord.ButtonStyle.success)
    async def economy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="💰 經濟與遊戲系統", color=0xf1c40f)
        embed.add_field(name="!balance / !錢包", value="查看資產總覽", inline=True)
        embed.add_field(name="!ATM / !銀行", value="💡 開啟銀行 ATM 介面", inline=True)
        embed.add_field(name="!kuji / !一番賞", value="💡 抽星空一番賞", inline=False)
        embed.add_field(name="!work / !工作", value="互動式打工賺錢", inline=True)
        embed.add_field(name="!gamble / !賭博", value="比大小對賭", inline=True)
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="🔍 資訊/其它", style=discord.ButtonStyle.secondary)
    async def info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🔍 資訊查詢與趣味功能", color=0x95a5a6)
        embed.add_field(name="!weather / !天氣", value="查全球氣象", inline=True)
        embed.add_field(name="!stock / !股價", value="查台股/美股", inline=True)
        embed.add_field(name="!fortune / !運勢", value="每日占卜", inline=True)
        embed.add_field(name="!profile / !等級", value="個人等級 XP", inline=True)
        await interaction.edit_original_response(embed=embed)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
            await interaction.edit_original_response(content=f"❌ Help 面板發生錯誤: {error}")
        else:
            await interaction.followup.send(f"❌ Help 面板發生錯誤: {error}", ephemeral=True)

@bot.command(name='help', aliases=['幫助', '求救'])
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