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

ADMIN_IDS = [1113353915010920452, 501251225715474433]

app = Flask(__name__)
bot_instance = None
loop_instance = None
TOKEN_FILE = "webpanel_token.json"

def load_token():
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get("token", "")
        except: pass
    return ""

def save_token(token):
    import json
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        json.dump({"token": token}, f)

panel_token = load_token()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yokaro Dash | 系統控制中心</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root {
            --sidebar-bg: #202225;
            --main-bg: #36393f;
            --header-bg: #2f3136;
            --card-bg: #2f3136;
            --accent: #5865f2;
            --text-primary: #ffffff;
            --text-secondary: #b9bbbe;
            --danger: #ed4245;
            --input-bg: #202225;
        }
        * { box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--main-bg);
            color: var(--text-primary);
            margin: 0;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        .sidebar {
            width: 260px;
            background-color: var(--sidebar-bg);
            display: flex;
            flex-direction: column;
            padding: 20px 0;
            border-right: 1px solid rgba(0,0,0,0.2);
        }
        .sidebar-brand {
            padding: 0 24px 24px;
            font-size: 18px;
            font-weight: 600;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .nav-item {
            padding: 12px 24px;
            color: var(--text-secondary);
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 12px;
            transition: 0.2s;
            cursor: pointer;
            font-size: 14px;
        }
        .nav-item:hover, .nav-item.active {
            background-color: rgba(255,255,255,0.05);
            color: var(--text-primary);
        }
        .nav-item.active { border-left: 4px solid var(--accent); padding-left: 20px; background-color: rgba(88,101,242,0.1); }
        
        .content { flex: 1; display: flex; flex-direction: column; }
        header {
            height: 56px;
            background-color: var(--header-bg);
            display: flex;
            align-items: center;
            padding: 0 24px;
            justify-content: space-between;
            box-shadow: 0 1px 0 rgba(0,0,0,0.2);
        }
        .stats-bar { display: flex; gap: 24px; font-size: 13px; color: var(--text-secondary); }
        .stats-bar b { color: var(--text-primary); font-weight: 600; }

        main { flex: 1; padding: 24px; overflow-y: auto; }
        .grid { display: grid; grid-template-columns: 320px 1fr; gap: 24px; height: 100%; }
        .card { background-color: var(--card-bg); border-radius: 8px; padding: 20px; display: flex; flex-direction: column; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px;}
        .card-label { font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 12px; letter-spacing: 0.5px; }
        
        select, input, button {
            width: 100%;
            background-color: var(--input-bg);
            border: 1px solid rgba(0,0,0,0.3);
            color: #dcddde;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 16px;
            outline: none;
            font-family: inherit;
            font-size: 14px;
        }
        button { background-color: var(--accent); color: white; border: none; cursor: pointer; font-weight: 600; transition: 0.2s; }
        button:hover { background-color: #4752c4; }
        button.secondary { background-color: #4f545c; }
        button.danger { background-color: var(--danger); }

        .chat-box {
            flex: 1;
            background-color: rgba(0,0,0,0.1);
            border-radius: 4px;
            overflow-y: auto;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 16px;
            min-height: 400px;
        }
        .msg { font-size: 14px; border-bottom: 1px solid rgba(255,255,255,0.03); padding-bottom: 8px; }
        .msg-meta { font-size: 11px; color: var(--text-secondary); margin-bottom: 4px; }
        .msg-author { font-weight: 600; color: #fff; margin-right: 6px; }
        .msg.bot .msg-author { color: var(--accent); }

        .mode-tabs { display: flex; gap: 8px; margin-bottom: 20px; }
        .mode-tabs button { margin-bottom: 0; padding: 8px; }

        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-thumb { background: #202225; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-brand"><i class="fas fa-bolt"></i> Yokaro Dash</div>
        <div class="nav-item active" id="nav-comm" onclick="switchPage('comm')"><i class="fas fa-comments"></i> 控制中心</div>
        <div class="nav-item" id="nav-stats" onclick="switchPage('stats')"><i class="fas fa-microchip"></i> 系統日誌</div>
        <div class="nav-item" style="margin-top: auto; color: var(--danger)" onclick="revoke()"><i class="fas fa-key"></i> 註銷連結</div>
    </div>

    <div class="content">
        <header>
            <div id="page-title" style="font-weight: 600">控制中心</div>
            <div class="stats-bar" id="top-stats">連線中...</div>
        </header>

        <main>
            <div class="grid" id="comm-view">
                <div class="card">
                    <div class="card-label">目標選擇</div>
                    <div class="mode-tabs">
                        <button id="btn-server" onclick="setMode('server')">伺服器</button>
                        <button id="btn-dm" onclick="setMode('dm')" class="secondary">私訊</button>
                    </div>

                    <div id="pane-server">
                        <label class="card-label">伺服器</label>
                        <select id="g-sel" onchange="loadChannels()"></select>
                        <label class="card-label">頻道</label>
                        <select id="c-sel" onchange="switchChat()"></select>
                    </div>

                    <div id="pane-dm" style="display:none">
                        <label class="card-label">最近對話</label>
                        <select id="d-sel" onchange="switchChat(true)"></select>
                        <label class="card-label">手動 ID</label>
                        <input type="text" id="d-id" onchange="switchChat()">
                    </div>

                    <div class="card-label" style="margin-top:20px">語音廣播</div>
                    <select id="v-sel"></select>
                    <div style="display:flex; gap:8px">
                        <button onclick="joinVoice()">進入</button>
                        <button onclick="leaveVoice()" class="danger">離開</button>
                    </div>
                </div>

                <div class="card">
                    <div class="card-label" id="chat-label">即時訊息串流</div>
                    <div class="chat-box" id="chat-box">請選擇一個頻道開始通訊...</div>
                    <div style="display:flex; gap:12px">
                        <input type="text" id="m-in" placeholder="以此身分發送訊息..." onkeypress="if(event.key==='Enter') send()">
                        <button style="width:100px" onclick="send()">發送</button>
                    </div>
                </div>
            </div>

            <div id="stats-view" style="display:none">
                <div class="card">
                    <div class="card-label">效能即時監控</div>
                    <div id="full-stats" style="line-height: 2">正在獲取數據...</div>
                </div>
            </div>
        </main>
    </div>

    <script>
        const token = new URLSearchParams(window.location.search).get('token');
        let mode = 'server', target = '', lastCount = 0;

        async function api(path, method='GET', body=null) {
            const h = { 'Authorization': token };
            if(body) h['Content-Type']='application/json';
            const r = await fetch(path, { method, headers: h, body: body?JSON.stringify(body):null });
            return r.json();
        }

        async function updateStats() {
            const d = await api('/api/stats');
            document.getElementById('top-stats').innerHTML = `<span>CPU: <b>${d.cpu_temp}°C</b></span><span>RAM: <b>${d.ram_mb}MB</b></span><span>Ping: <b>${d.latency}ms</b></span>`;
            if(document.getElementById('stats-view').style.display !== 'none') {
                document.getElementById('full-stats').innerHTML = `<p>CPU 使用率: <b>${d.cpu_percent}%</b></p><p>CPU 溫度: <b>${d.cpu_temp}°C</b></p><p>記憶體佔用: <b>${d.ram_mb} MB</b></p><p>API 延遲: <b>${d.latency} ms</b></p><p>所在伺服器: <b>${d.guilds}</b></p>`;
            }
        }

        function switchPage(p) {
            document.getElementById('nav-comm').classList.toggle('active', p==='comm');
            document.getElementById('nav-stats').classList.toggle('active', p==='stats');
            document.getElementById('comm-view').style.display = p==='comm' ? 'grid' : 'none';
            document.getElementById('stats-view').style.display = p==='stats' ? 'block' : 'none';
            document.getElementById('page-title').innerText = p==='comm' ? '控制中心' : '系統日誌';
        }

        function setMode(m) {
            mode = m;
            document.getElementById('pane-server').style.display = m==='server' ? 'block' : 'none';
            document.getElementById('pane-dm').style.display = m==='dm' ? 'block' : 'none';
            document.getElementById('btn-server').className = m==='server' ? '' : 'secondary';
            document.getElementById('btn-dm').className = m==='dm' ? '' : 'secondary';
            target = '';
        }

        async function loadChannels() {
            const gid = document.getElementById('g-sel').value;
            const d = await api(`/api/channels/${gid}`);
            const cs = document.getElementById('c-sel'); cs.innerHTML = '<option value="">選擇頻道...</option>';
            d.text.forEach(c => cs.innerHTML += `<option value="${c.id}">#${c.name}</option>`);
            const vs = document.getElementById('v-sel'); vs.innerHTML = '<option value="">選擇語音...</option>';
            d.voice.forEach(c => vs.innerHTML += `<option value="${c.id}">${c.name}</option>`);
        }

        function switchChat(isDMSel = false) {
            if(mode==='server') target = document.getElementById('c-sel').value;
            else {
                if(isDMSel) { target = document.getElementById('d-sel').value; document.getElementById('d-id').value = target; }
                else target = document.getElementById('d-id').value;
            }
            lastCount = 0;
            document.getElementById('chat-box').innerHTML = '載入訊息串...';
            poll();
        }

        async function poll() {
            if(!target) return;
            const ms = await api(mode === 'server' ? `/api/chat/${target}` : `/api/dm/${target}`);
            if(ms.length !== lastCount) {
                const box = document.getElementById('chat-box'); box.innerHTML = '';
                ms.reverse().forEach(m => {
                    box.innerHTML += `<div class="msg ${m.is_bot?'bot':''}"><div class="msg-meta">${m.time}</div><span class="msg-author">${m.author}:</span>${m.content}</div>`;
                });
                box.scrollTop = box.scrollHeight; lastCount = ms.length;
            }
        }

        async function send() {
            const i = document.getElementById('m-in'), t = i.value;
            if(!t || !target) return; i.value = '';
            await api(mode==='server'?'/api/send':'/api/dm/send', 'POST', mode==='server'?{channel_id:target,content:t}:{user_id:target,content:t});
            setTimeout(poll, 500);
        }

        async function joinVoice() { const cid = document.getElementById('v-sel').value; if(cid) api('/api/voice/join','POST',{channel_id:cid}); }
        async function leaveVoice() { const gid = document.getElementById('g-sel').value; if(gid) api('/api/voice/leave','POST',{guild_id:gid}); }
        function revoke() { if(confirm('確定註銷？')) window.location.href = `/api/revoke?token=${token}`; }

        (async () => {
            updateStats(); setInterval(updateStats, 5000); setInterval(poll, 2000);
            const gs = await api('/api/guilds');
            const gsel = document.getElementById('g-sel'); gsel.innerHTML = '<option>選擇伺服器...</option>';
            gs.forEach(g => gsel.innerHTML += `<option value="${g.id}">${g.name}</option>`);
            const ds = await api('/api/dm_list');
            const dsel = document.getElementById('d-sel'); dsel.innerHTML = '<option>選擇私訊...</option>';
            ds.forEach(d => dsel.innerHTML += `<option value="${d.id}">${d.name}</option>`);
        })();
    </script>
</body>
</html>
"""

def auth_required(f):
    def wrapper(*args, **kwargs):
        if request.headers.get('Authorization') != panel_token and request.args.get('token') != panel_token:
            return jsonify({"error": "Unauthorized"}), 403
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route("/")
@auth_required
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/stats")
@auth_required
def api_stats():
    temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
    temp = 0
    if temps and 'coretemp' in temps: temp = temps['coretemp'][0].current
    
    return jsonify({
        "cpu_temp": temp,
        "cpu_percent": psutil.cpu_percent(),
        "ram_mb": int(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024),
        "latency": round(bot_instance.latency * 1000),
        "guilds": len(bot_instance.guilds)
    })

@app.route("/api/revoke")
def api_revoke():
    import json
    global panel_token
    auth = request.args.get("token")
    if auth != panel_token: return "Unauthorized", 403
    
    # 建立新 Token 並存檔 (讓舊的徹底失效)
    new_token = secrets.token_urlsafe(24)
    panel_token = new_token
    save_token(new_token)
    
    # 建立一個異步任務來關閉隧道並重啟機器人
    def shutdown():
        import time, os
        time.sleep(2) # 讓網頁有時間傳回響應
        cog = bot_instance.get_cog('WebPanelCog')
        if cog and cog.tunnel_process:
            cog.tunnel_process.terminate()
        os._exit(0) # 強制結束進程，觸發 Pterodactyl 自動重啟

    threading.Thread(target=shutdown).start()

    return """
    <body style="background:#202225; color:white; font-family:sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; text-align:center;">
        <div>
            <h1 style="color:#ed4245; font-size:48px;">🔒 系統已註銷</h1>
            <p style="font-size:20px;">安全隧道已關閉，端口已釋放。</p>
            <p style="color:#b9bbbe;">機器人正在執行安全重啟... 請稍後在 Discord 重新獲取連結。</p>
            <script>setTimeout(() => { window.close(); }, 5000);</script>
        </div>
    </body>
    """

@app.route("/api/guilds")
@auth_required
def api_guilds():
    return jsonify([{"id": str(g.id), "name": g.name} for g in bot_instance.guilds])

@app.route("/api/channels/<guild_id>")
@auth_required
def api_channels(guild_id):
    guild = bot_instance.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Guild not found"}), 404
    return jsonify({
        "text": [{"id": str(c.id), "name": c.name} for c in guild.text_channels],
        "voice": [{"id": str(c.id), "name": c.name} for c in guild.voice_channels]
    })

@app.route("/api/chat/<channel_id>")
@auth_required
def api_chat(channel_id):
    channel = bot_instance.get_channel(int(channel_id))
    if not channel: return jsonify([])
    
    async def fetch_history():
        msgs = []
        async for m in channel.history(limit=50):
            content = m.clean_content
            if not content and m.embeds:
                if m.embeds[0].description:
                    content = f"[卡片] {m.embeds[0].description}"
                elif m.embeds[0].title:
                    content = f"[卡片] {m.embeds[0].title}"
                else:
                    content = "[卡片訊息]"
            elif not content:
                content = "[附件/圖片]"
                
            msgs.append({
                "author": m.author.display_name,
                "content": content,
                "time": m.created_at.strftime("%H:%M:%S"),
                "is_bot": m.author.id == bot_instance.user.id
            })
        return msgs

    future = asyncio.run_coroutine_threadsafe(fetch_history(), loop_instance)
    return jsonify(future.result())

@app.route("/api/dm_list")
@auth_required
def api_dm_list():
    dms = []
    for user in bot_instance.users:
        if user.dm_channel:
            dms.append({"id": str(user.id), "name": user.display_name})
    return jsonify(dms[:50])

@app.route("/api/dm/<user_id>")
@auth_required
def api_dm(user_id):
    async def fetch_dm():
        try:
            user = await bot_instance.fetch_user(int(user_id))
            if not user.dm_channel:
                await user.create_dm()
            
            msgs = []
            async for m in user.dm_channel.history(limit=50):
                content = m.clean_content
                if not content and m.embeds:
                    if m.embeds[0].description:
                        content = f"[卡片] {m.embeds[0].description}"
                    elif m.embeds[0].title:
                        content = f"[卡片] {m.embeds[0].title}"
                    else:
                        content = "[卡片訊息]"
                elif not content:
                    content = "[附件/圖片]"

                msgs.append({
                    "author": m.author.display_name,
                    "content": content,
                    "time": m.created_at.strftime("%H:%M:%S"),
                    "is_bot": m.author.id == bot_instance.user.id
                })
            return msgs
        except Exception as e:
            return {"error": f"無法載入私訊紀錄: {str(e)}"}

    future = asyncio.run_coroutine_threadsafe(fetch_dm(), loop_instance)
    return jsonify(future.result())

@app.route("/api/send", methods=['POST'])
@auth_required
def api_send():
    data = request.json
    channel = bot_instance.get_channel(int(data['channel_id']))
    if channel:
        asyncio.run_coroutine_threadsafe(channel.send(data['content']), loop_instance)
    return jsonify({"status": "ok"})

@app.route("/api/dm/send", methods=['POST'])
@auth_required
def api_dm_send():
    data = request.json
    async def send_dm():
        user = await bot_instance.fetch_user(int(data['user_id']))
        if user:
            await user.send(data['content'])
    asyncio.run_coroutine_threadsafe(send_dm(), loop_instance)
    return jsonify({"status": "ok"})

@app.route("/api/voice/join", methods=['POST'])
@auth_required
def api_join():
    data = request.json
    channel = bot_instance.get_channel(int(data['channel_id']))
    if channel:
        async def join():
            if channel.guild.voice_client:
                await channel.guild.voice_client.move_to(channel)
            else:
                await channel.connect()
        asyncio.run_coroutine_threadsafe(join(), loop_instance)
    return jsonify({"status": "ok"})

@app.route("/api/voice/leave", methods=['POST'])
@auth_required
def api_leave():
    import json
    data = request.json
    guild = bot_instance.get_guild(int(data['guild_id']))
    if guild and guild.voice_client:
        asyncio.run_coroutine_threadsafe(guild.voice_client.disconnect(), loop_instance)
    return jsonify({"status": "ok"})

class WebPanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        global bot_instance, loop_instance
        bot_instance = bot
        loop_instance = asyncio.get_event_loop()
        self.tunnel_process = None
        self.cert_path = "/home/container/.cloudflared/cert.pem"
        
        # 啟動時自動嘗試開啟隧道
        self.bot.loop.create_task(self.auto_start_tunnel())
        
        # 啟動 Flask (使用百年證書加密)
        import random
        self.port = random.randint(6000, 9000)
        
        # --- 自動生成百年證書 ---
        if not os.path.exists("cert.pem") or not os.path.exists("key.pem"):
            print("📜 正在為大總裁鍛造百年加密證書...")
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:4096", 
                "-keyout", "key.pem", "-out", "cert.pem", 
                "-days", "36500", "-nodes", 
                "-subj", "/C=TW/ST=Taipei/L=Yokaro/O=YokaroBot/OU=Security/CN=yokaro.bot"
            ], capture_output=True)
            print("✅ 百年證書鍛造完成！有效期限至 2126 年。")

        def run_flask():
            try: subprocess.run(["fuser", "-k", f"{self.port}/tcp"], capture_output=True)
            except: pass
            try:
                print(f"📡 Flask (HTTPS) 正在啟動於端口: {self.port}")
                # 啟用 SSL
                app.run(host="0.0.0.0", port=self.port, debug=False, use_reloader=False, ssl_context=('cert.pem', 'key.pem'))
            except Exception as e: print(f"⚠️ Flask 啟動失敗: {e}")
        threading.Thread(target=run_flask, daemon=True).start()
        
        # --- 自動啟動隧道 ---
        asyncio.run_coroutine_threadsafe(self.auto_start_tunnel(), self.bot.loop)

    @commands.group(name='tunnel')
    async def tunnel_group(self, ctx):
        if ctx.author.id not in ADMIN_IDS: return
        if ctx.invoked_subcommand is None:
            await ctx.send("📡 **隧道管理中心**\n`!tunnel login` - 登入 Cloudflare\n`!tunnel setup <域名>` - 創建並綁定域名\n`!tunnel start` - 切換至正式模式")

    @tunnel_group.command(name='login')
    async def tunnel_login(self, ctx):
        await ctx.send("🔑 **正在獲取 Cloudflare 授權連結...**")
        
        proc = await asyncio.create_subprocess_shell(
            "./cloudflared tunnel login",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        found_url = False
        try:
            while True:
                line = await proc.stdout.readline()
                if not line: break
                text = line.decode().strip()
                print(f"[Tunnel Login] {text}")
                
                match = re.search(r'https://dash\.cloudflare\.com/argotunnel\?callback=[^\s]+', text)
                if match:
                    url = match.group(0)
                    embed = discord.Embed(title="🔑 Cloudflare 授權請求", color=0xf38020)
                    embed.description = f"請點擊下方連結登入並授權：\n\n🔗 **[點此授權登入]({url})**\n\n授權後請回到這裡輸入 `!tunnel setup <您的域名>`"
                    await ctx.send(embed=embed)
                    found_url = True
                    break
            
            if not found_url: await ctx.send("❌ 無法抓取到連結，請檢查控制台。")
        except Exception as e: await ctx.send(f"❌ 錯誤: {e}")

    @tunnel_group.command(name='setup')
    async def tunnel_setup(self, ctx, domain: str):
        await ctx.send(f"🛠️ **正在為 {domain} 及其子域名進行雙重綁定...**")
        try:
            # 1. 創建隧道 (如果已存在會跳過)
            subprocess.run(["./cloudflared", "tunnel", "create", "yokaro-bot"], capture_output=True, text=True)
            # 2. 綁定主域名
            subprocess.run(["./cloudflared", "tunnel", "route", "dns", "yokaro-bot", domain], capture_output=True, text=True)
            # 3. 綁定 stat 子域名
            stat_domain = f"stat.{domain}"
            subprocess.run(["./cloudflared", "tunnel", "route", "dns", "yokaro-bot", stat_domain], capture_output=True, text=True)
            
            with open(".env", "a") as f:
                f.write(f"\nCUSTOM_DOMAIN={domain}\nNAMED_TUNNEL=yokaro-bot")
            
            os.environ["CUSTOM_DOMAIN"] = domain
            os.environ["NAMED_TUNNEL"] = "yokaro-bot"
                
            await ctx.send(f"✅ **設置完成！**\n主域名: `{domain}`\n狀態頁面: `https://{stat_domain}`\n請輸入 `!tunnel start` 啟動！")
        except Exception as e:
            await ctx.send(f"❌ 設置失敗: {e}")

# --- 狀態頁面 HTML 模板 (純金 Liquid Gold 旗艦版) ---
STAT_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ user.display_name }} | Live Status</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root {
            --gold: linear-gradient(135deg, #bf953f, #fcf6ba, #b38728, #fbf5b7, #aa771c);
            --bg: #0a0a0a;
            --glass: rgba(255, 255, 255, 0.03);
        }
        body {
            margin: 0; background: var(--bg); color: white; font-family: 'Outfit', sans-serif;
            display: flex; justify-content: center; align-items: center; min-height: 100vh;
            background-image: radial-gradient(circle at 50% 50%, #1a1a1a, #000);
            overflow: hidden;
        }
        .gold-border {
            position: relative; padding: 2px; border-radius: 40px;
            background: var(--gold);
            box-shadow: 0 0 50px rgba(191, 149, 63, 0.3);
            animation: rotate 10s linear infinite;
        }
        @keyframes rotate { 0% { filter: hue-rotate(0deg); } 100% { filter: hue-rotate(360deg); } }
        
        .card {
            background: rgba(10,10,10,0.9);
            backdrop-filter: blur(50px);
            border-radius: 38px;
            width: 450px; padding: 40px;
            display: flex; flex-direction: column; align-items: center;
        }
        .avatar-wrap {
            position: relative; width: 150px; height: 150px; margin-bottom: 25px;
        }
        .avatar {
            width: 100%; height: 100%; border-radius: 50%; border: 4px solid #bf953f;
            box-shadow: 0 0 30px rgba(191, 149, 63, 0.5);
        }
        .status-dot {
            position: absolute; bottom: 10px; right: 10px; width: 25px; height: 25px;
            border-radius: 50%; border: 4px solid #000;
        }
        .online { background: #2ed573; box-shadow: 0 0 15px #2ed573; }
        .dnd { background: #ff4757; box-shadow: 0 0 15px #ff4757; }
        .idle { background: #ffa502; box-shadow: 0 0 15px #ffa502; }
        .offline { background: #747d8c; }

        h1 { font-size: 32px; font-weight: 800; background: var(--gold); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 10px 0; }
        .tag { color: #888; font-size: 14px; margin-bottom: 30px; }

        .activity-card {
            width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(191, 149, 63, 0.2);
            border-radius: 24px; padding: 20px; display: flex; align-items: center; gap: 20px;
            margin-bottom: 20px;
        }
        .activity-icon { width: 60px; height: 60px; border-radius: 12px; object-fit: cover; }
        .activity-info h2 { font-size: 16px; margin: 0; color: #fcf6ba; }
        .activity-info p { font-size: 13px; margin: 5px 0 0; color: #aaa; }

        .footer { font-size: 12px; color: #444; margin-top: 20px; letter-spacing: 2px; }
    </style>
</head>
<body>
    <div class="gold-border">
        <div class="card">
            <div class="avatar-wrap">
                <img src="{{ user.display_avatar.url }}" class="avatar">
                <div class="status-dot {{ status }}"></div>
            </div>
            <h1>{{ user.display_name }}</h1>
            <div class="tag">@{{ user.name }}</div>

            {% if activity %}
            <div class="activity-card">
                <img src="{{ activity.large_image_url or 'https://cdn-icons-png.flaticon.com/512/681/681392.png' }}" class="activity-icon">
                <div class="activity-info">
                    <h2>正在遊玩 {{ activity.name }}</h2>
                    <p>{{ activity.details or '' }}</p>
                    <p>{{ activity.state or '' }}</p>
                </div>
            </div>
            {% else %}
            <div style="color:#555; font-size:14px; margin: 20px 0;">目前沒有活動中 💤</div>
            {% endif %}

            <div class="footer">STAT.WAYNA1015.CCWU.CC</div>
        </div>
    </div>
    <script>setTimeout(() => location.reload(), 15000);</script>
</body>
</html>
"""

@app.route("/api/status/<int:user_id>")
def user_status_page(user_id):
    from flask import render_template_string
    user = bot_instance.get_user(user_id)
    if not user: return "User not found", 404
    
    # 找尋 Presence (需要伺服器成員)
    member = None
    for guild in bot_instance.guilds:
        member = guild.get_member(user_id)
        if member: break
    
    if not member: return "Member not found in any common guild", 404
    
    status = str(member.status)
    activity = None
    for act in member.activities:
        if act.type == discord.ActivityType.playing or act.type == discord.ActivityType.listening:
            activity = act
            break
            
    return render_template_string(STAT_HTML_TEMPLATE, user=member, status=status, activity=activity)

    @tunnel_group.command(name='start')
    async def tunnel_start(self, ctx):
        if self.tunnel_process: 
            self.tunnel_process.terminate()
            await asyncio.sleep(2) # 等待舊進程關閉
            
        # 確保記憶已同步
        domain = os.environ.get("CUSTOM_DOMAIN", "yokaro.wayna1015.ccwu.cc")
        self.tunnel_url = f"https://{domain}"
        
        asyncio.run_coroutine_threadsafe(self.auto_start_tunnel(), self.bot.loop)
        await ctx.send(f"🚀 **正在切換至正式模式...**\n請稍候 5-10 秒後訪問: {self.tunnel_url}")

    async def auto_start_tunnel(self):
        await asyncio.sleep(5)
        domain = os.environ.get("CUSTOM_DOMAIN")
        named = os.environ.get("NAMED_TUNNEL")
        
        import platform
        dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        if platform.system() == "Windows": dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        if not os.path.exists("./cloudflared"):
            subprocess.run(["curl", "-L", dl_url, "-o", "cloudflared"])
            if platform.system() != "Windows": subprocess.run(["chmod", "+x", "cloudflared"])

        try:
            if named:
                print(f"🚀 [自動化] 正在連線至您的專屬域名: {domain}...")
                # 指定 Pterodactyl 的 .cloudflared 路徑
                cred_path = "/home/container/.cloudflared"
                self.tunnel_process = subprocess.Popen(
                    ["./cloudflared", "tunnel", "--no-autoupdate", "run", "--url", f"https://localhost:{self.port}", "--no-tls-verify", named],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    env={**os.environ, "CLOUDFLARED_HOME": cred_path}
                )
                self.tunnel_url = f"https://{domain}"
                print(f"✅ [正式模式] 隧道已建立: {self.tunnel_url}")
            else:
                print("📡 [臨時模式] 啟動 trycloudflare 隧道...")
                self.tunnel_process = subprocess.Popen(
                    ["./cloudflared", "tunnel", "--url", f"https://localhost:{self.port}", "--no-tls-verify"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
                for _ in range(30):
                    await asyncio.sleep(1)
                    line = self.tunnel_process.stdout.readline()
                    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                    if match:
                        self.tunnel_url = match.group(0)
                        print(f"✅ [臨時模式] 隧道建立完成: {self.tunnel_url}")
                        break
        except Exception as e: print(f"❌ 隧道自動啟動失敗: {e}")

    @commands.command(name='webpanel')
    async def open_panel(self, ctx):
        if ctx.author.id not in ADMIN_IDS: return await ctx.send("❌ 此為大總裁專屬儀表板。")
        
        global panel_token
        if not panel_token or panel_token == "":
            panel_token = secrets.token_urlsafe(24)
            save_token(panel_token)
        
        # 強制重置隧道
        if self.tunnel_url:
            if self.tunnel_process and self.tunnel_process.poll() is not None:
                self.tunnel_url = ""
        
        await ctx.send(f"📡 正在建立安全隧道 (Port: {self.port})...")
        
        if self.tunnel_url:
            full_url = f"{self.tunnel_url}/?token={panel_token}"
            revoke_url = f"{self.tunnel_url}/api/revoke?token={panel_token}"
            embed = discord.Embed(title="🌌 Yokaro 系統中樞連線資訊", color=0xff0080)
            embed.description = f"您的後台連結為永久有效，除非點擊註銷。\n\n🔗 **[點此進入管理面板]({full_url})**\n\n🚨 **[危急時點此註銷所有網址]({revoke_url})**"
            try:
                await ctx.author.send(embed=embed)
                await ctx.send("✅ 連結已發送到您的私訊！")
            except:
                await ctx.send(f"❌ 無法私訊您，請開啟私訊功能。")
            return

        # 下載/檢查 cloudflared...
        import platform
        dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        if platform.system() == "Windows": dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        if not os.path.exists("./cloudflared"):
            await ctx.send("📡 正在安裝隧道核心...")
            subprocess.run(["curl", "-L", dl_url, "-o", "cloudflared"])
            if platform.system() != "Windows": subprocess.run(["chmod", "+x", "cloudflared"])

        try:
            if self.tunnel_process: self.tunnel_process.terminate()
            self.tunnel_process = subprocess.Popen(
                ["./cloudflared", "tunnel", "--url", f"http://localhost:{self.port}"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            
            for _ in range(30):
                await asyncio.sleep(0.5)
                line = self.tunnel_process.stdout.readline()
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if match:
                    self.tunnel_url = match.group(0)
                    break
                    
            if self.tunnel_url:
                full_url = f"{self.tunnel_url}/?token={panel_token}"
                revoke_url = f"{self.tunnel_url}/api/revoke?token={panel_token}"
                embed = discord.Embed(title="🌌 Yokaro 系統中樞連線資訊", color=0xff0080)
                embed.description = f"您的後台連結為永久有效，除非點擊註銷。\n\n🔗 **[點此進入管理面板]({full_url})**\n\n🚨 **[危急時點此註銷所有網址]({revoke_url})**"
                await ctx.author.send(embed=embed)
                await ctx.send("✅ **安全隧道已建立，永久密鑰已發送至您的私訊！**")
            else: await ctx.send("❌ 無法獲取隧道網址。")
        except Exception as e:
            await ctx.send(f"❌ 隧道啟動失敗: {e}")

async def setup(bot):
    await bot.add_cog(WebPanelCog(bot))
