import discord
from discord.ext import commands
import asyncio
import subprocess
import os
import secrets
import threading
import re
import json
from flask import Flask, render_template_string, request, jsonify
import psutil

# 管理員名單
ADMIN_IDS = [1113353915010920452, 501251225715474433, 467554275921494017]

app = Flask(__name__)
bot_instance = None
loop_instance = None
TOKEN_FILE = "webpanel_token.json"
panel_token = ""

def load_token():
    global panel_token
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                panel_token = json.load(f).get("token", "")
        except: pass
    if not panel_token:
        panel_token = secrets.token_urlsafe(24)
        save_token(panel_token)

def save_token(token):
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        json.dump({"token": token}, f)

load_token()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>Yokaro Dash | 系統控制中心</title>
    <style>
        body { font-family: sans-serif; background: #36393f; color: white; padding: 20px; }
        .card { background: #2f3136; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        button { background: #5865f2; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-right: 10px; }
        button:hover { background: #4752c4; }
        button.danger { background: #ed4245; }
        .status-item { margin-bottom: 10px; font-size: 14px; color: #b9bbbe; }
        b { color: #fff; }
    </style>
</head>
<body>
    <h1>Yokaro 系統控制中心</h1>
    
    <div class="card">
        <h3>🚀 機器人管理</h3>
        <button onclick="manage('sync')">同步全域指令 (Sync)</button>
        <button onclick="manage('restart')" class="danger">強制重啟機器人</button>
    </div>

    <div class="card">
        <h3>📊 系統狀態</h3>
        <div id="stats-content">載入中...</div>
    </div>

    <script>
        const token = new URLSearchParams(window.location.search).get('token');
        async function manage(action) {
            if(action === 'restart' && !confirm('確定要重啟嗎？')) return;
            const res = await fetch(`/api/system/${action}?token=${token}`, { method: 'POST' });
            const data = await res.json();
            alert(data.message || '執行成功');
            if(action === 'sync') location.reload();
        }

        async function updateStats() {
            try {
                const res = await fetch(`/api/stats?token=${token}`);
                const data = await res.json();
                document.getElementById('stats-content').innerHTML = `
                    <div class="status-item">CPU 使用率: <b>${data.cpu}%</b></div>
                    <div class="status-item">記憶體使用率: <b>${data.memory}%</b></div>
                    <div class="status-item">伺服器數量: <b>${data.guilds}</b></div>
                    <div class="status-item">已註冊模組: <b>${data.cogs.join(', ')}</b></div>
                `;
            } catch(e) { console.error(e); }
        }
        setInterval(updateStats, 5000);
        updateStats();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    auth = request.args.get("token")
    if auth != panel_token: return "Unauthorized", 403
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
def api_stats():
    auth = request.args.get("token")
    if auth != panel_token: return "Unauthorized", 403
    return jsonify({
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "guilds": len(bot_instance.guilds),
        "cogs": list(bot_instance.cogs.keys())
    })

@app.route('/api/system/sync', methods=['POST'])
def api_sync():
    auth = request.args.get("token")
    if auth != panel_token: return "Unauthorized", 403
    async def do_sync():
        await bot_instance.tree.sync()
        print("🚀 [WebPanel] 全域指令同步完成")
    asyncio.run_coroutine_threadsafe(do_sync(), loop_instance)
    return jsonify({"message": "同步指令請求已發送"})

@app.route('/api/system/restart', methods=['POST'])
def api_restart():
    auth = request.args.get("token")
    if auth != panel_token: return "Unauthorized", 403
    threading.Thread(target=lambda: os._exit(0)).start()
    return jsonify({"message": "機器人正在重啟..."})

class WebPanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        global bot_instance, loop_instance
        bot_instance = bot
        loop_instance = asyncio.get_event_loop()
        self.tunnel_process = None
        self.tunnel_url = ""
        self.port = 8848
        
        # 啟動 Flask (使用 HTTP，由外部隧道處理 HTTPS)
        threading.Thread(target=lambda: app.run(host="0.0.0.0", port=self.port, debug=False, use_reloader=False), daemon=True).start()
        # 啟動隧道
        self.bot.loop.create_task(self.auto_start_tunnel())

    async def auto_start_tunnel(self):
        domain = os.getenv("CUSTOM_DOMAIN")
        tunnel_name = os.getenv("NAMED_TUNNEL", "yokaro-bot")
        
        env = os.environ.copy()
        env["CLOUDFLARED_HOME"] = "/home/container/.cloudflared"
        
        try:
            # 停掉舊的 cloudflared
            subprocess.run(["pkill", "-f", "cloudflared"], capture_output=True)
            await asyncio.sleep(2)
            
            # 對接至本地 Flask 埠號
            cmd = ["/home/container/cloudflared", "tunnel", "--no-tls-verify", "run", "--url", f"http://127.0.0.1:{self.port}"]
            if tunnel_name: cmd.append(tunnel_name)
            
            self.tunnel_process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            if domain:
                self.tunnel_url = f"https://{domain}"
                print(f"✅ [WebPanel] 具名隧道啟動: {self.tunnel_url}")
            else:
                for _ in range(20):
                    await asyncio.sleep(1)
                    line = self.tunnel_process.stdout.readline()
                    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                    if match:
                        self.tunnel_url = match.group(0)
                        print(f"✅ [WebPanel] 隨機隧道連通: {self.tunnel_url}")
                        break
        except Exception as e:
            print(f"❌ [WebPanel] 隧道啟動失敗: {e}")

    @commands.command(name='webpanel', aliases=['wp'])
    async def webpanel_cmd(self, ctx):
        """獲取管理面板連結"""
        if ctx.author.id not in ADMIN_IDS:
            return await ctx.send("❌ 此為大總裁專屬功能。")
        
        domain = os.getenv("CUSTOM_DOMAIN")
        base_url = f"https://{domain}" if domain else self.tunnel_url
        if not base_url: base_url = f"http://localhost:{self.port}"
        
        url = f"{base_url}/?token={panel_token}"
        embed = discord.Embed(title="🌌 Yokaro 系統中樞", color=0x5865f2)
        embed.description = f"大總裁，這是您的管理連結：\n\n🔗 **[點此進入後台介面]({url})**"
        try:
            await ctx.author.send(embed=embed)
            await ctx.send("✅ 連結已發送到您的私訊！")
        except:
            await ctx.send(f"❌ 無法私訊您，請開啟私訊功能。")

async def setup(bot):
    await bot.add_cog(WebPanelCog(bot))
