import discord
from discord.ext import commands
import asyncio
import subprocess
import os
import secrets
import threading
import re
from flask import Flask, render_template_string, request

# ── 大總裁專屬設定 ──
ADMIN_IDS = [1113353915010920452, 501251225715474433]

app = Flask(__name__)
panel_token = ""
bot_instance = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yokaro Pro Admin Panel</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;600&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Outfit', sans-serif; background: #0f0c29; color: white; margin: 0; padding: 20px; overflow-x: hidden; }
        .container { max-width: 800px; margin: auto; background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border-radius: 20px; padding: 30px; border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        h1 { color: #ff0080; text-align: center; font-weight: 600; text-shadow: 0 0 10px #ff0080; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px; margin-top: 30px; }
        .stat-card { background: rgba(0,0,0,0.3); padding: 20px; border-radius: 15px; text-align: center; transition: 0.3s; }
        .stat-card:hover { transform: translateY(-5px); border: 1px solid #ff0080; }
        .stat-value { font-size: 24px; color: #00d2ff; display: block; margin-top: 5px; }
        .controls { margin-top: 40px; display: flex; justify-content: center; gap: 15px; flex-wrap: wrap; }
        button { background: linear-gradient(45deg, #ff0080, #7928ca); border: none; color: white; padding: 12px 25px; border-radius: 10px; cursor: pointer; font-weight: 600; transition: 0.3s; }
        button:hover { filter: brightness(1.2); box-shadow: 0 0 15px #ff0080; }
        .token-display { background: #000; padding: 10px; border-radius: 5px; color: #39ff14; font-family: monospace; text-align: center; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌌 優卡洛 核心管理中心</h1>
        <div class="stats-grid">
            <div class="stat-card"><span>伺服器數量</span><span class="stat-value">{{ guild_count }}</span></div>
            <div class="stat-card"><span>目前語音連線</span><span class="stat-value">{{ voice_count }}</span></div>
            <div class="stat-card"><span>系統延遲</span><span class="stat-value">{{ latency }}ms</span></div>
        </div>
        
        <div class="controls">
            <form action="/reboot" method="post"><button type="submit">🚀 系統冷啟動</button></form>
            <form action="/clear_cache" method="post"><button style="background: #444" type="submit">🧹 清理暫存</button></form>
        </div>

        <div class="token-display">🔒 當前訪問授權: {{ token }}</div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    if request.args.get('token') != panel_token:
        return "<h1>403 Forbidden</h1><p>大總裁，請透過 Discord 獲取正確的亂碼連結喔！🐾</p>", 403
    
    return render_template_string(HTML_TEMPLATE, 
                                 guild_count=len(bot_instance.guilds),
                                 voice_count=len(bot_instance.voice_clients),
                                 latency=round(bot_instance.latency * 1000),
                                 token=panel_token)

@app.route("/reboot", methods=['POST'])
def reboot():
    os._exit(0)

class WebPanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        global bot_instance
        bot_instance = bot
        self.tunnel_process = None

    @commands.command(name='webpanel')
    async def open_panel(self, ctx):
        if ctx.author.id not in ADMIN_IDS: return await ctx.send("❌ 此為大總裁專屬儀表板。")
        
        global panel_token
        panel_token = secrets.token_urlsafe(24) # 生成極長亂碼密碼
        
        await ctx.send("📡 **正在加密生成安全隧道連結...**")
        
        # 確認 cloudflared 是否存在，若無則自動下載
        if not os.path.exists("./cloudflared"):
            await ctx.send("📡 **首次啟動隧道，洛洛正在自動下載 Cloudflared 核心套件 (Linux)...**")
            subprocess.run(["curl", "-L", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "-o", "cloudflared"])
            subprocess.run(["chmod", "+x", "cloudflared"])

        # 啟動隧道
        try:
            self.tunnel_process = subprocess.Popen(
                ["./cloudflared", "tunnel", "--url", "http://localhost:5000"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            
            url = ""
            for _ in range(30):
                await asyncio.sleep(0.5)
                line = self.tunnel_process.stdout.readline()
                if ".trycloudflare.com" in line:
                    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                    if match: url = match.group(0); break
            
            if url:
                full_url = f"{url}?token={panel_token}"
                embed = discord.Embed(title="🔐 優卡洛 終極管理權限已開啟", color=0xff0080)
                embed.description = f"大總裁，這是您的專屬加密連結：\n\n**[立即進入儀表板]({full_url})**\n\n此連結具備 **TryCloudflare** 加密，且後綴包含動態 Token。點擊下方按鈕即可馬上銷毀。"
                
                view = discord.ui.View()
                btn = discord.ui.Button(label="立即註銷網址", style=discord.ButtonStyle.danger)
                
                async def burn(interaction):
                    self.tunnel_process.terminate()
                    self.tunnel_process = None
                    await interaction.response.edit_message(content="✅ **安全隧道已關閉，連結已銷毀。**", embed=None, view=None)
                
                btn.callback = burn; view.add_item(btn)
                await ctx.send(embed=embed, view=view)
        except Exception as e: await ctx.send(f"❌ 隧道啟動失敗: {e}")

    def cog_unload(self):
        if self.tunnel_process: self.tunnel_process.terminate()

async def setup(bot):
    # 啟動 Flask
    threading.Thread(target=lambda: app.run(port=5000, debug=False, use_reloader=False), daemon=True).start()
    await bot.add_cog(WebPanelCog(bot))
