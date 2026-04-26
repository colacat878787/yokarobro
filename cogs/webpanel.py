import discord
from discord.ext import commands
import asyncio
import subprocess
import os
import secrets
import threading
import re
from flask import Flask, render_template_string, request, jsonify
import psutil

ADMIN_IDS = [1113353915010920452, 501251225715474433]

app = Flask(__name__)
panel_token = ""
bot_instance = None
loop_instance = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yokaro Pro Admin Panel</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #0f0c29; --glass: rgba(255, 255, 255, 0.05); --border: rgba(255, 255, 255, 0.1); --primary: #ff0080; --secondary: #7928ca; --text: #fff; }
        body { font-family: 'Outfit', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }
        .glass-panel { background: var(--glass); backdrop-filter: blur(12px); border: 1px solid var(--border); border-radius: 20px; padding: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); margin-bottom: 20px; }
        h1, h2 { color: var(--primary); text-shadow: 0 0 10px rgba(255,0,128,0.5); margin-top: 0; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .stat-card { background: rgba(0,0,0,0.4); padding: 15px; border-radius: 12px; text-align: center; }
        .stat-value { font-size: 24px; color: #00d2ff; font-weight: 600; display: block; margin-top: 5px; }
        .dashboard-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 20px; margin-top: 20px; }
        select, input, button { background: rgba(0,0,0,0.5); border: 1px solid var(--border); color: white; padding: 10px; border-radius: 8px; width: 100%; font-family: 'Outfit', sans-serif; margin-bottom: 10px; box-sizing: border-box; }
        button { background: linear-gradient(45deg, var(--primary), var(--secondary)); cursor: pointer; font-weight: 600; border: none; transition: 0.3s; }
        button:hover { filter: brightness(1.2); box-shadow: 0 0 15px var(--primary); }
        .chat-container { display: flex; flex-direction: column; height: 500px; background: rgba(0,0,0,0.6); border-radius: 10px; padding: 15px; margin-bottom: 10px; }
        .chat-box { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding-right: 5px; }
        .msg { background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px; font-size: 14px; width: fit-content; max-width: 80%; }
        .msg.bot { background: rgba(255,0,128,0.2); border-left: 3px solid var(--primary); align-self: flex-end; }
        .msg span { font-size: 11px; color: #bbb; display: block; margin-bottom: 4px; }
        
        .tabs { display: flex; gap: 10px; margin-bottom: 15px; }
        .tab-btn { flex: 1; background: rgba(255,255,255,0.1); border: none; padding: 10px; border-radius: 8px; cursor: pointer; color: white; font-weight: 600; }
        .tab-btn.active { background: var(--primary); box-shadow: 0 0 10px var(--primary); }
        
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); border-radius: 10px; }
        ::-webkit-scrollbar-thumb { background: var(--primary); border-radius: 10px; }
    </style>
</head>
<body>
    <div class="glass-panel">
        <h1>🌌 Yokaro 系統中樞</h1>
        <div class="stats-grid" id="stats">讀取中...</div>
    </div>

    <div class="dashboard-grid">
        <div class="glass-panel">
            <div class="tabs">
                <button class="tab-btn active" id="tab-server" onclick="switchTab('server')">🌍 伺服器通訊</button>
                <button class="tab-btn" id="tab-dm" onclick="switchTab('dm')">👤 私訊 (DM)</button>
            </div>
            
            <div id="panel-server">
                <label>選擇伺服器</label>
                <select id="guild-select" onchange="loadChannels()"><option value="">請選擇...</option></select>
                
                <label>文字頻道 (通訊用)</label>
                <select id="text-channel-select" onchange="switchChat()"></select>

                <label>語音頻道 (播音用)</label>
                <select id="voice-channel-select"></select>
                <div style="display:flex; gap:10px;">
                    <button onclick="joinVoice()">🎤 進入</button>
                    <button onclick="leaveVoice()" style="background: #e74c3c">🛑 離開</button>
                </div>
            </div>

            <div id="panel-dm" style="display:none;">
                <label>請輸入使用者 ID</label>
                <input type="text" id="dm-user-id" placeholder="例如: 1113353915010920452" onchange="switchChat()">
                <button onclick="switchChat()">載入私訊紀錄</button>
            </div>
        </div>

        <div class="glass-panel">
            <h2 id="chat-title">💬 遠端通訊介面</h2>
            <div class="chat-container">
                <div class="chat-box" id="chat-box">請在左側選擇頻道或使用者...</div>
            </div>
            <div style="display:flex; gap:10px;">
                <input type="text" id="msg-input" placeholder="以優卡洛的身分發言..." onkeypress="if(event.key === 'Enter') sendMessage()">
                <button style="width:100px" onclick="sendMessage()">發送</button>
            </div>
        </div>
    </div>

    <script>
        const token = new URLSearchParams(window.location.search).get('token');
        let currentMode = 'server'; // 'server' or 'dm'
        let currentTarget = '';
        let chatLoop = null;
        let lastMsgCount = 0;

        async function fetchAPI(endpoint, method='GET', body=null) {
            const opts = { method, headers: { 'Authorization': token } };
            if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
            const res = await fetch(endpoint, opts);
            return res.json();
        }

        async function updateStats() {
            const data = await fetchAPI('/api/stats');
            document.getElementById('stats').innerHTML = `
                <div class="stat-card">CPU 溫度/使用率<span class="stat-value">${data.cpu_temp}°C / ${data.cpu_percent}%</span></div>
                <div class="stat-card">記憶體用量<span class="stat-value">${data.ram_mb} MB</span></div>
                <div class="stat-card">系統延遲<span class="stat-value">${data.latency} ms</span></div>
                <div class="stat-card">活躍伺服器<span class="stat-value">${data.guilds}</span></div>
            `;
        }

        async function init() {
            updateStats();
            setInterval(updateStats, 5000);
            
            const guilds = await fetchAPI('/api/guilds');
            const sel = document.getElementById('guild-select');
            guilds.forEach(g => {
                const opt = document.createElement('option');
                opt.value = g.id; opt.textContent = g.name;
                sel.appendChild(opt);
            });
            
            // 啟動 1.5 秒即時輪詢引擎 (Real-time polling)
            chatLoop = setInterval(pollChat, 1500);
        }

        function switchTab(mode) {
            currentMode = mode;
            document.getElementById('tab-server').classList.toggle('active', mode === 'server');
            document.getElementById('tab-dm').classList.toggle('active', mode === 'dm');
            document.getElementById('panel-server').style.display = mode === 'server' ? 'block' : 'none';
            document.getElementById('panel-dm').style.display = mode === 'dm' ? 'block' : 'none';
            
            document.getElementById('chat-title').innerText = mode === 'server' ? '💬 頻道通訊介面' : '👤 私訊 (DM) 介面';
            document.getElementById('chat-box').innerHTML = '請選擇目標...';
            currentTarget = '';
        }

        async function loadChannels() {
            const gid = document.getElementById('guild-select').value;
            if(!gid) return;
            const data = await fetchAPI(`/api/channels/${gid}`);
            
            const txt = document.getElementById('text-channel-select');
            txt.innerHTML = '<option value="">請選擇...</option>';
            data.text.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id; opt.textContent = `#${c.name}`;
                txt.appendChild(opt);
            });

            const voc = document.getElementById('voice-channel-select');
            voc.innerHTML = '<option value="">請選擇...</option>';
            data.voice.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id; opt.textContent = `🔊 ${c.name}`;
                voc.appendChild(opt);
            });
        }

        function switchChat() {
            if (currentMode === 'server') {
                currentTarget = document.getElementById('text-channel-select').value;
            } else {
                currentTarget = document.getElementById('dm-user-id').value.trim();
            }
            lastMsgCount = 0;
            document.getElementById('chat-box').innerHTML = "讀取中...";
            pollChat(true); // force scroll to bottom on first load
        }

        async function pollChat(forceScroll = false) {
            if (!currentTarget) return;
            
            let msgs = [];
            if (currentMode === 'server') {
                msgs = await fetchAPI(`/api/chat/${currentTarget}`);
            } else {
                msgs = await fetchAPI(`/api/dm/${currentTarget}`);
            }
            
            if (msgs.error) {
                if (lastMsgCount !== -1) {
                    document.getElementById('chat-box').innerHTML = `<div class="msg">❌ ${msgs.error}</div>`;
                    lastMsgCount = -1;
                }
                return;
            }

            if (msgs.length !== lastMsgCount || forceScroll) {
                const box = document.getElementById('chat-box');
                const isScrolledToBottom = box.scrollHeight - box.clientHeight <= box.scrollTop + 50;
                
                box.innerHTML = "";
                msgs.reverse().forEach(m => {
                    box.innerHTML += `<div class="msg ${m.is_bot ? 'bot' : ''}"><span>${m.time} | ${m.author}</span>${m.content}</div>`;
                });
                lastMsgCount = msgs.length;
                
                if (forceScroll || isScrolledToBottom) {
                    box.scrollTop = box.scrollHeight;
                }
            }
        }

        async function sendMessage() {
            const input = document.getElementById('msg-input');
            const txt = input.value.trim();
            if(!currentTarget || !txt) return;
            
            input.value = ""; // 清空輸入框
            
            if (currentMode === 'server') {
                await fetchAPI('/api/send', 'POST', { channel_id: currentTarget, content: txt });
            } else {
                await fetchAPI('/api/dm/send', 'POST', { user_id: currentTarget, content: txt });
            }
            pollChat(true); // 立刻刷新
        }

        async function joinVoice() {
            const cid = document.getElementById('voice-channel-select').value;
            if(!cid) return;
            await fetchAPI('/api/voice/join', 'POST', { channel_id: cid });
            alert("已加入語音頻道");
        }

        async function leaveVoice() {
            const gid = document.getElementById('guild-select').value;
            if(!gid) return;
            await fetchAPI('/api/voice/leave', 'POST', { guild_id: gid });
            alert("已退出語音頻道");
        }

        init();
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
            msgs.append({
                "author": m.author.display_name,
                "content": m.clean_content or "[附件/圖片]",
                "time": m.created_at.strftime("%H:%M:%S"),
                "is_bot": m.author.id == bot_instance.user.id
            })
        return msgs

    future = asyncio.run_coroutine_threadsafe(fetch_history(), loop_instance)
    return jsonify(future.result())

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
                msgs.append({
                    "author": m.author.display_name,
                    "content": m.clean_content or "[附件/圖片]",
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
        loop_instance = bot.loop
        self.tunnel_process = None

    @commands.command(name='webpanel')
    async def open_panel(self, ctx):
        if ctx.author.id not in ADMIN_IDS: return await ctx.send("❌ 此為大總裁專屬儀表板。")
        
        global panel_token
        panel_token = secrets.token_urlsafe(24)
        
        if not os.path.exists("./cloudflared"):
            await ctx.send("📡 **首次啟動隧道，洛洛正在自動下載 Cloudflared 核心套件 (Linux)...**")
            subprocess.run(["curl", "-L", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "-o", "cloudflared"])
            subprocess.run(["chmod", "+x", "cloudflared"])

        try:
            if self.tunnel_process: self.tunnel_process.terminate()
            self.tunnel_process = subprocess.Popen(
                ["./cloudflared", "tunnel", "--url", "http://localhost:5000"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            
            url = ""
            for _ in range(30):
                await asyncio.sleep(0.5)
                line = self.tunnel_process.stdout.readline()
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if match:
                    url = match.group(0)
                    break
                    
            if url:
                await ctx.author.send(f"🌌 **Yokaro 總部最高許可權儀表板 (極速通訊版)**\n連結: {url}/?token={panel_token}\n\n⚠️ 此連結具備破壞性與完全控制權限，請勿外流。")
                await ctx.send("✅ **安全隧道已建立，密鑰已發送至您的私訊！**")
                
                def run_flask():
                    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
                threading.Thread(target=run_flask, daemon=True).start()
                
            else: await ctx.send("❌ 無法獲取隧道網址。")
        except Exception as e:
            await ctx.send(f"❌ 隧道啟動失敗: {e}")

async def setup(bot):
    await bot.add_cog(WebPanelCog(bot))
