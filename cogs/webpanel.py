import discord
from discord.ext import commands
import asyncio
import subprocess
import os
import secrets
import threading
import re
import json
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import psutil

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'image')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/image/<path:filename>')
def serve_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


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


# ===== 伺服器後台 Token (每個伺服器獨立金鑰) =====
SERVER_TOKEN_FILE = "server_panel_tokens.json"

def load_server_tokens():
    if os.path.exists(SERVER_TOKEN_FILE):
        try:
            with open(SERVER_TOKEN_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_server_tokens(data):
    with open(SERVER_TOKEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def get_server_token(guild_id):
    data = load_server_tokens()
    gid = str(guild_id)
    if gid not in data or not data.get(gid):
        data[gid] = secrets.token_urlsafe(16)
        save_server_tokens(data)
    return data[gid]

load_token()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>Yokaro Dash | 系統控制中心</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #e2e8f0;
            background: #020617;
        }
        * { box-sizing: border-box; }
        body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top, rgba(59, 130, 246, 0.18), transparent 22%), linear-gradient(180deg, #020617 0%, #090e1a 100%); }
        main { max-width: 1180px; margin: 0 auto; padding: 28px 24px 40px; }
        .topbar { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 18px; align-items: center; margin-bottom: 24px; }
        .hero { display: grid; gap: 14px; }
        h1 { margin: 0; font-size: clamp(2rem, 3vw, 2.6rem); letter-spacing: -0.04em; }
        .hero p { margin: 0; color: #94a3b8; line-height: 1.75; }
        .panel-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 20px; }
        .panel { background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(148, 163, 184, 0.1); box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28); border-radius: 24px; padding: 24px; }
        .panel-8 { grid-column: span 8; }
        .panel-4 { grid-column: span 4; }
        .panel-full { grid-column: span 12; }
        .panel h2 { margin-top: 0; color: #f8fafc; font-size: 1.1rem; }
        .panel p { margin: 0; color: #cbd5e1; }
        .stats-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 20px; }
        .stat-card { background: rgba(148, 163, 184, 0.08); border: 1px solid rgba(148, 163, 184, 0.12); border-radius: 18px; padding: 18px; }
        .stat-card strong { display: block; font-size: 1.95rem; color: #fff; }
        .stat-card span { color: #94a3b8; font-size: 0.95rem; }
        label { display: block; margin-bottom: 8px; color: #cbd5e1; font-size: 0.95rem; }
        input, select, textarea { width: 100%; border-radius: 16px; border: 1px solid rgba(148, 163, 184, 0.14); background: rgba(15, 23, 42, 0.92); color: #f8fafc; padding: 14px 16px; font-size: 0.95rem; }
        textarea { min-height: 150px; resize: vertical; }
        input[type=file] { padding: 12px 10px; }
        .hint { margin-top: 6px; color: #94a3b8; font-size: 0.9rem; }
        .button-row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 18px; }
        button { border: none; border-radius: 16px; padding: 14px 20px; font-size: 0.98rem; font-weight: 600; cursor: pointer; transition: transform .16s ease, box-shadow .16s ease; }
        button:hover { transform: translateY(-1px); }
        .btn-primary { background: linear-gradient(135deg, #3b82f6, #2563eb); color: #fff; box-shadow: 0 18px 45px rgba(37, 99, 235, 0.22); }
        .btn-secondary { background: rgba(148, 163, 184, 0.12); color: #f8fafc; }
        .btn-danger { background: #ef4444; color: #fff; }
        .status-pill { display: inline-flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 999px; background: rgba(59, 130, 246, 0.12); color: #7dd3fc; font-size: 0.92rem; }
        .preview-box { margin-top: 18px; padding: 20px; border-radius: 22px; background: rgba(15, 23, 42, 0.96); border: 1px solid rgba(148, 163, 184, 0.12); min-height: 170px; }
        .preview-box h3 { margin: 0 0 12px; font-size: 1rem; }
        .preview-box p { margin: 0; color: #cbd5e1; white-space: pre-wrap; }
        .tag { display: inline-flex; gap: 8px; align-items: center; background: rgba(15, 23, 42, 0.88); border: 1px solid rgba(148, 163, 184, 0.14); border-radius: 999px; padding: 10px 14px; color: #cbd5e1; font-size: 0.88rem; }
        .bottom-note { margin-top: 16px; color: #94a3b8; font-size: 0.9rem; }
        @media (max-width: 980px) { .panel-8, .panel-4, .panel-full { grid-column: span 12; } }
    </style>
</head>
<body>
    <main>
        <div class="topbar">
            <div class="hero">
                <h1>Yokaro Control Center</h1>
                <p>一個更像 App 的管理面板，讓你用機器人身份快速發送公告、私訊成員、上傳圖片與管理系統狀態。</p>
            </div>
            <div class="button-row">
                <button class="btn-secondary" onclick="manage('sync')">同步指令</button>
                <button class="btn-danger" onclick="manage('restart')">重新啟動</button>
            </div>
        </div>

        <div class="panel-grid">
            <section class="panel panel-8">
                <h2>📊 系統總覽</h2>
                <div class="stats-grid">
                    <div class="stat-card"><strong id="stat-guilds">0</strong><span>伺服器數量</span></div>
                    <div class="stat-card"><strong id="stat-cpu">0%</strong><span>CPU 使用率</span></div>
                    <div class="stat-card"><strong id="stat-memory">0%</strong><span>記憶體使用率</span></div>
                    <div class="stat-card"><strong id="stat-cogs">0</strong><span>已啟用模組</span></div>
                </div>
                <div class="preview-box" style="margin-top: 24px;">
                    <h3>即時狀態</h3>
                    <p id="stats-content">正在取得機器人狀態…</p>
                </div>
            </section>

            <section class="panel panel-4">
                <h2>🧠 快速操作</h2>
                <p>這裡可以快速執行常見管理命令，適合緊急或維運情境使用。</p>
                <div class="button-row">
                    <button class="btn-primary" onclick="manage('sync')">同步全域指令</button>
                    <button class="btn-danger" onclick="manage('restart')">強制重啟</button>
                </div>
                <div class="bottom-note">機器人正在執行中時，可立即更新或重啟。</div>
            </section>

            <section class="panel panel-full">
                <h2>📣 內容發送中心</h2>
                <div class="stats-grid" style="grid-template-columns: 1fr 1fr; gap: 16px;">
                    <div>
                        <label for="target-type">發送方式</label>
                        <select id="target-type" name="target_type">
                            <option value="server">頻道廣播</option>
                            <option value="dm">私訊所有成員</option>
                        </select>
                        <p class="hint">選擇私訊後，系統會向伺服器內可私訊成員發送內容。</p>
                    </div>
                    <div>
                        <label for="guild-select">選擇伺服器</label>
                        <select id="guild-select" name="guild_id"></select>
                    </div>
                </div>
                <div class="stats-grid" style="grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 18px;">
                    <div>
                        <label for="channel-select">選擇頻道</label>
                        <select id="channel-select" name="channel_id"></select>
                        <p class="hint">若選擇私訊模式，可忽略此欄位。</p>
                    </div>
                    <div>
                        <label for="file">上傳圖片（可選）</label>
                        <input id="file" name="file" type="file" accept="image/*">
                        <p class="hint">支援單張圖片上傳，可搭配文字內容一起發送。</p>
                    </div>
                </div>
                <label for="message">訊息內容</label>
                <textarea id="message" name="message" placeholder="在此撰寫要發送的公告或私訊內容…"></textarea>

                <div class="button-row" style="margin-top: 18px;">
                    <button type="button" class="btn-primary" onclick="submitBroadcast()">🚀 立即發送</button>
                    <button type="button" class="btn-secondary" onclick="updatePreview()">預覽訊息</button>
                </div>

                <div class="preview-box">
                    <h3>訊息預覽</h3>
                    <p id="preview-text">請輸入文字或上傳圖片，然後按「預覽訊息」。</p>
                    <div style="margin-top: 14px; display: flex; flex-wrap: wrap; gap: 10px;">
                        <span class="tag">伺服器：<span id="preview-guild">尚未選擇</span></span>
                        <span class="tag">頻道：<span id="preview-channel">尚未選擇</span></span>
                        <span class="tag">模式：<span id="preview-mode">頻道廣播</span></span>
                    </div>
                </div>

                <div class="bottom-note" id="status">已就緒，點擊「立即發送」開始推播。</div>
            </section>
        </div>
    </main>

    <script>
        const token = new URLSearchParams(window.location.search).get('token');
        const guildSelect = document.getElementById('guild-select');
        const channelSelect = document.getElementById('channel-select');
        const targetType = document.getElementById('target-type');
        const statusBox = document.getElementById('status');
        const previewText = document.getElementById('preview-text');
        const previewGuild = document.getElementById('preview-guild');
        const previewChannel = document.getElementById('preview-channel');
        const previewMode = document.getElementById('preview-mode');
        const statGuilds = document.getElementById('stat-guilds');
        const statCpu = document.getElementById('stat-cpu');
        const statMemory = document.getElementById('stat-memory');
        const statCogs = document.getElementById('stat-cogs');

        async function manage(action) {
            if(action === 'restart' && !confirm('確定要重啟嗎？')) return;
            const res = await fetch(`/api/system/${action}?token=${token}`, { method: 'POST' });
            const data = await res.json();
            alert(data.message || '執行成功');
            if(action === 'sync') loadStatistics();
        }

        async function loadStatistics() {
            try {
                const res = await fetch(`/api/stats?token=${token}`);
                const data = await res.json();
                statGuilds.textContent = data.guilds;
                statCpu.textContent = `${data.cpu}%`;
                statMemory.textContent = `${data.memory}%`;
                statCogs.textContent = data.cogs.length;
                document.getElementById('stats-content').innerHTML = `目前已連線 <b>${data.guilds}</b> 個伺服器，模組：<b>${data.cogs.join(', ')}</b>`;
            } catch (e) {
                console.error(e);
                document.getElementById('stats-content').textContent = '取得系統狀態失敗。';
            }
        }

        async function loadGuilds() {
            try {
                const res = await fetch(`/api/discord/guilds?token=${token}`);
                const data = await res.json();
                guildSelect.innerHTML = '';
                if (!data.guilds || !data.guilds.length) {
                    guildSelect.innerHTML = '<option value="">無可用伺服器</option>';
                    return;
                }
                data.guilds.forEach(g => {
                    const opt = document.createElement('option');
                    opt.value = g.id;
                    opt.textContent = g.name;
                    guildSelect.appendChild(opt);
                });
                await loadChannels(guildSelect.value);
            } catch (e) {
                console.error(e);
            }
        }

        async function loadChannels(guildId) {
            try {
                const res = await fetch(`/api/discord/guilds/${guildId}/channels?token=${token}`);
                const data = await res.json();
                channelSelect.innerHTML = '';
                if (!data.channels || !data.channels.length) {
                    channelSelect.innerHTML = '<option value="">此伺服器沒有可發訊的文字頻道</option>';
                    return;
                }
                data.channels.forEach(ch => {
                    const opt = document.createElement('option');
                    opt.value = ch.id;
                    opt.textContent = ch.name;
                    channelSelect.appendChild(opt);
                });
            } catch (e) {
                console.error(e);
            }
        }

        function updatePreview() {
            const message = document.getElementById('message').value.trim();
            previewText.textContent = message || '目前尚未輸入任何文字內容。';
            previewGuild.textContent = guildSelect.selectedOptions[0]?.textContent || '尚未選擇';
            previewChannel.textContent = channelSelect.selectedOptions[0]?.textContent || '尚未選擇';
            previewMode.textContent = targetType.value === 'dm' ? '私訊所有成員' : '頻道廣播';
            statusBox.textContent = '已更新預覽。確認後點擊「立即發送」。';
            statusBox.style.color = '#7dd3fc';
        }

        async function submitBroadcast() {
            statusBox.textContent = '發送中，請稍候...';
            statusBox.style.color = '#f8fafc';
            const formData = new FormData();
            formData.set('token', token);
            formData.set('target_type', targetType.value);
            formData.set('guild_id', guildSelect.value);
            formData.set('channel_id', channelSelect.value);
            formData.set('message', document.getElementById('message').value.trim());
            const fileInput = document.getElementById('file');
            if (fileInput.files.length > 0) {
                formData.append('file', fileInput.files[0]);
            }
            const res = await fetch('/api/discord/broadcast', { method: 'POST', body: formData });
            const data = await res.json();
            statusBox.textContent = data.message || '發送完成';
            statusBox.style.color = res.ok ? '#7dd3fc' : '#f87171';
        }

        guildSelect.addEventListener('change', () => loadChannels(guildSelect.value));
        targetType.addEventListener('change', () => {
            channelSelect.disabled = targetType.value === 'dm';
        });

        loadStatistics();
        loadGuilds();
    </script>
</body>
</html>
"""


SERVER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>優卡洛 伺服器後台</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root{font-family:'Inter','Segoe UI',Tahoma,sans-serif;color:#e2e8f0;background:#0b1220;}
  *{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at top,rgba(56,189,248,.16),transparent 22%),linear-gradient(180deg,#0b1220,#101a2e);}
  main{max-width:960px;margin:0 auto;padding:28px 20px 40px}
  .card{background:rgba(17,26,44,.92);border:1px solid rgba(148,163,184,.14);border-radius:20px;padding:22px;margin-bottom:20px}
  h1{margin:0 0 4px;font-size:1.8rem}
  .sub{color:#94a3b8;margin:0 0 18px}
  .guild-head{display:flex;gap:16px;align-items:center}
  .guild-head img{width:64px;height:64px;border-radius:16px}
  .stat{font-size:.95rem;color:#cbd5e1;margin:2px 0}
  .toggle{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border:1px solid rgba(148,163,184,.14);border-radius:14px;margin-bottom:10px;background:rgba(148,163,184,.06)}
  .toggle .nm{font-weight:600}
  .toggle .dc{color:#94a3b8;font-size:.85rem;margin-top:2px}
  .switch{position:relative;width:52px;height:28px;flex-shrink:0}
  .switch input{opacity:0;width:0;height:0}
  .slider{position:absolute;inset:0;background:#334155;border-radius:28px;transition:.25s;cursor:pointer}
  .slider:before{content:"";position:absolute;width:22px;height:22px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.25s}
  .switch input:checked + .slider{background:#2ecc71}
  .switch input:checked + .slider:before{transform:translateX(24px)}
  label{display:block;margin:14px 0 6px;color:#cbd5e1;font-size:.92rem}
  input[type=text],input[type=number]{width:100%;padding:12px 14px;border-radius:12px;border:1px solid rgba(148,163,184,.2);background:#0f1a30;color:#f8fafc;font-size:.95rem}
  .row{display:flex;gap:10px;flex-wrap:wrap}
  .btn{border:none;border-radius:12px;padding:11px 18px;font-weight:600;cursor:pointer;background:#334155;color:#fff}
  .btn.primary{background:linear-gradient(135deg,#3b82f6,#6366f1)}
  .btn.green{background:linear-gradient(135deg,#10b981,#059669)}
  .toast{position:fixed;bottom:22px;right:22px;background:#111827;border:1px solid #2ecc71;color:#d1fae5;padding:12px 18px;border-radius:12px;display:none;z-index:9}
</style>
</head>
<body>
<main>
  <h1>⚙️ 優卡洛 伺服器後台</h1>
  <p class="sub">管理優卡洛在本伺服器內的功能</p>
  <div class="card">
    <div class="guild-head">
      <img id="gicon" alt="" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7">
      <div>
        <div style="font-size:1.3rem;font-weight:700" id="gname">載入中...</div>
        <div class="stat" id="gmeta"></div>
      </div>
    </div>
  </div>
  <div class="card">
    <h2>功能開關</h2>
    <div id="modules">載入中...</div>
  </div>
  <div class="card">
    <h2>伺服器設定</h2>
    <label>經驗值倍率 (XP Rate)</label>
    <div class="row">
      <input type="number" id="xp_rate" step="0.1" min="0.1" placeholder="1.0">
      <button class="btn primary" onclick="saveSetting('xp_rate')">儲存</button>
    </div>
    <label>歡迎頻道 ID (留空 = 關閉)</label>
    <div class="row">
      <input type="text" id="welcome_channel" placeholder="頻道 ID">
      <button class="btn primary" onclick="saveSetting('welcome_channel')">儲存</button>
    </div>
    <label>日誌頻道 ID</label>
    <div class="row">
      <input type="text" id="log_channel" placeholder="頻道 ID">
      <button class="btn primary" onclick="saveSetting('log_channel')">儲存</button>
    </div>
  </div>
  <button class="btn green" onclick="refresh()">🔄 重新整理</button>
</main>

<div class="toast" id="toast"></div>
<script>
  const GID = {{guild_id}};
  const KEY = "{{key}}";
  function toast(m){const t=document.getElementById('toast');t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',2500);}
  async function api(url, opts){
    opts=opts||{};opts.method=opts.method||'GET';opts.headers=opts.headers||{};
    if(opts.body&&typeof opts.body!=='string'){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(opts.body);}
    const r=await fetch(url,opts);return r.json();
  }
  async function refresh(){
    const d=await api(`/api/server/info?guild=${GID}&key=${KEY}`);
    if(d.error){document.getElementById('gname').textContent='權限不足';return;}
    document.getElementById('gname').textContent=d.guild.name;
    document.getElementById('gmeta').textContent=`👥 ${d.guild.members} 位成員 | ID: ${d.guild.id}`;
    if(d.guild.icon)document.getElementById('gicon').src=d.guild.icon;
    const s=d.settings;
    document.getElementById('xp_rate').value=s.xp_rate||1;
    document.getElementById('welcome_channel').value=s.welcome_channel||'';
    document.getElementById('log_channel').value=s.log_channel||'';
    const box=document.getElementById('modules');box.innerHTML='';
    for(const m of d.modules){
      const div=document.createElement('div');div.className='toggle';
      div.innerHTML=`<div><div class="nm">${m.name}</div><div class="dc">${m.desc}</div></div>
        <label class="switch"><input type="checkbox" ${m.state?'checked':''} onchange="toggleMod('${m.key}',this.checked)"><span class="slider"></span></label>`;
      box.appendChild(div);
    }
  }
  async function toggleMod(key,enabled){
    const r=await api('/api/server/toggle',{method:'POST',body:{guild:GID,key:KEY,module:key,enabled}});
    toast(r.ok?('已更新 '+(enabled?'開啟':'關閉')):'失敗');
  }
  async function saveSetting(field){
    const el=document.getElementById(field);const v=el.value;
    const r=await api('/api/server/settings',{method:'POST',body:{guild:GID,key:KEY,field,value:v}});
    toast(r.ok?('已儲存 '+field):'失敗');
  }
  refresh();
</script>
</body>
</html>"""


PUBLIC_POLICY_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }} | Yokaro</title>
    <style>
        :root { color-scheme: dark; font-family: "Segoe UI", system-ui, sans-serif; color: #e5eefb; background: #07111f; }
        * { box-sizing: border-box; }
        body { margin: 0; min-height: 100vh; background: radial-gradient(circle at 15% 0%, rgba(56, 189, 248, .18), transparent 30%), linear-gradient(145deg, #07111f, #101b31); }
        main { width: min(900px, calc(100% - 32px)); margin: 0 auto; padding: 56px 0 72px; }
        header { margin-bottom: 28px; }
        .brand { color: #7dd3fc; font-size: .9rem; letter-spacing: .12em; text-transform: uppercase; }
        h1 { margin: 10px 0 8px; font-size: clamp(2rem, 5vw, 3.2rem); color: #f8fafc; }
        .updated { margin: 0; color: #9fb1c8; }
        article { padding: 30px; border: 1px solid rgba(148, 163, 184, .16); border-radius: 18px; background: rgba(15, 27, 48, .9); box-shadow: 0 24px 70px rgba(0, 0, 0, .24); }
        h2 { margin: 28px 0 10px; color: #bae6fd; font-size: 1.2rem; }
        h2:first-child { margin-top: 0; }
        p, li { color: #c7d4e5; line-height: 1.85; }
        ul { padding-left: 1.3rem; }
        a { color: #7dd3fc; }
        footer { margin-top: 22px; color: #8192aa; font-size: .9rem; }
        @media (max-width: 600px) { main { padding-top: 32px; } article { padding: 22px; } }
    </style>
</head>
<body>
    <main>
        <header>
            <div class="brand">Yokaro / 優卡洛</div>
            <h1>{{ title }}</h1>
            <p class="updated">最後更新：2026-08-19</p>
        </header>
        <article>{{ content|safe }}</article>
        <footer>本頁面適用於 Yokaro Discord 機器人及其相關服務。</footer>
    </main>
</body>
</html>
"""


TERMS_CONTENT = """
<h2>1. 服務說明</h2>
<p>Yokaro 是提供 Discord 伺服器管理、娛樂、資訊與互動功能的機器人服務。使用本服務即表示你同意遵守 Discord 的使用條款、社群規範，以及所在伺服器的管理規則。</p>
<h2>2. 使用規範</h2>
<ul>
    <li>不得利用 Yokaro 進行騷擾、詐騙、惡意散播、未經授權的資料蒐集或其他違法行為。</li>
    <li>不得嘗試破壞服務、繞過權限、濫用 API 或干擾其他使用者。</li>
    <li>伺服器管理員可以依伺服器規則停用功能或限制成員使用。</li>
</ul>
<h2>3. 服務變更與可用性</h2>
<p>功能可能因維護、Discord API 變更、第三方服務故障或安全因素而調整、暫停或移除。我們會盡力維持服務穩定，但不保證服務永遠不中斷或完全沒有錯誤。</p>
<h2>4. 第三方服務</h2>
<p>部分功能可能連接 Discord、Google Gemini、YouTube、Spotify 或其他第三方服務。這些服務有各自的條款與隱私政策，使用相關功能時也必須遵守其規範。</p>
<h2>5. 條款更新</h2>
<p>條款更新後會公布在本頁面。更新後繼續使用 Yokaro，即表示接受更新後的內容。</p>
"""


PRIVACY_CONTENT = """
<h2>1. 我們可能處理的資料</h2>
<ul>
    <li>Discord 使用者 ID、伺服器 ID、頻道 ID，以及執行功能所需的基本暱稱或顯示名稱。</li>
    <li>你主動輸入的設定、指令內容、問候訊息、提醒或遊戲資料。</li>
    <li>為了維持服務安全與除錯而產生的錯誤、操作與系統日誌。</li>
</ul>
<h2>2. 使用目的</h2>
<p>資料只用於提供機器人功能、保存個人或伺服器設定、處理管理操作、改善穩定性，以及偵測濫用或安全事件。</p>
<h2>3. 資料保存與刪除</h2>
<p>資料會依功能需要保存於機器人運行環境。當資料不再需要、功能被移除，或收到合理的刪除要求時，會視技術與備份狀況刪除或匿名化。</p>
<h2>4. 資料分享與安全</h2>
<p>除非為了提供你主動使用的第三方功能、遵守法律要求或處理安全事件，我們不會出售你的個人資料。網路傳輸與第三方服務仍可能存在風險，請勿透過機器人提交密碼、Token、信用卡號或其他敏感資訊。</p>
<h2>5. 你的權利</h2>
<p>如需查詢、修改或刪除與 Yokaro 相關的資料，請透過機器人的管理聯絡方式提出申請，並提供足以辨識資料的 Discord 使用者 ID 或伺服器 ID。</p>
<h2>6. 政策更新</h2>
<p>本隱私政策可能因功能或法律要求更新。最新版本會持續公布於本頁面。</p>
"""

@app.route('/term')
def terms_page():
    return render_template_string(
        PUBLIC_POLICY_TEMPLATE,
        title="服務條款",
        content=TERMS_CONTENT,
    )


@app.route('/privacy')
def privacy_page():
    return render_template_string(
        PUBLIC_POLICY_TEMPLATE,
        title="隱私與安全政策",
        content=PRIVACY_CONTENT,
    )


@app.route('/status')
def status_page():
    status = {
        "status": "ok",
        "bot_name": bot_instance.user.name if bot_instance and bot_instance.user else "starting",
        "guilds": len(bot_instance.guilds) if bot_instance and bot_instance.guilds else 0,
        "latency": round(bot_instance.latency * 1000) if bot_instance and bot_instance.latency else None,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return jsonify(status)


@app.route('/')
def index():
    # 檢查是否有 OAuth callback 參數
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    if code or state or error:
        # 委派給 OAuth cog 處理
        oauth_cog = bot_instance.get_cog('OAuthCog') if bot_instance else None
        if oauth_cog:
            return oauth_cog.oauth_callback_handler()
        return "OAuth module not loaded", 500
    
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

@app.route('/api/discord/guilds')
def api_discord_guilds():
    auth = request.args.get("token")
    if auth != panel_token: return "Unauthorized", 403
    if not bot_instance:
        return jsonify({"guilds": []})

    guilds = []
    for guild in sorted(bot_instance.guilds, key=lambda g: g.name.lower()):
        channels = []
        for channel in sorted(guild.text_channels, key=lambda c: (c.position, c.name)):
            if channel.permissions_for(guild.me).send_messages:
                channels.append({"id": str(channel.id), "name": f"#{channel.name}"})
        guilds.append({"id": str(guild.id), "name": guild.name, "channels": channels[:20]})
    return jsonify({"guilds": guilds})

@app.route('/api/discord/guilds/<guild_id>/channels')
def api_discord_channels(guild_id):
    auth = request.args.get("token")
    if auth != panel_token: return "Unauthorized", 403
    if not bot_instance:
        return jsonify({"channels": []})

    guild = bot_instance.get_guild(int(guild_id))
    if not guild:
        return jsonify({"channels": []})

    channels = []
    for channel in sorted(guild.text_channels, key=lambda c: (c.position, c.name)):
        if channel.permissions_for(guild.me).send_messages:
            channels.append({"id": str(channel.id), "name": f"#{channel.name}"})
    return jsonify({"channels": channels})

@app.route('/api/discord/broadcast', methods=['POST'])
def api_discord_broadcast():
    auth = request.form.get("token") or request.args.get("token")
    if auth != panel_token: return "Unauthorized", 403
    if not bot_instance or not loop_instance:
        return jsonify({"message": "機器人尚未就緒", "success": False}), 500

    target_type = (request.form.get("target_type") or "server").strip()
    guild_id = request.form.get("guild_id", "").strip()
    channel_id = request.form.get("channel_id", "").strip()
    message = (request.form.get("message") or "").strip()
    uploaded_file = request.files.get("file")

    if not message and not uploaded_file:
        return jsonify({"message": "請輸入訊息內容或上傳圖片", "success": False}), 400

    async def do_broadcast():
        try:
            file_path = None
            filename = None
            if uploaded_file and uploaded_file.filename:
                filename = secure_filename(uploaded_file.filename)
                if not filename:
                    filename = f"upload_{secrets.token_hex(4)}.png"
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                uploaded_file.save(file_path)

            if target_type == "dm":
                guild = bot_instance.get_guild(int(guild_id)) if guild_id else None
                if not guild:
                    guild = bot_instance.guilds[0] if bot_instance.guilds else None
                if not guild:
                    raise RuntimeError("沒有可用伺服器")

                sent = 0
                for member in guild.members:
                    if member.bot or member.pending:
                        continue
                    try:
                        if file_path:
                            with open(file_path, 'rb') as f:
                                send_file = discord.File(f, filename=filename)
                                await member.send(content=message or None, file=send_file)
                        else:
                            await member.send(content=message or None)
                        sent += 1
                    except Exception:
                        continue
                return {"message": f"已私訊 {sent} 位成員", "success": True}

            guild = bot_instance.get_guild(int(guild_id)) if guild_id else None
            if not guild:
                guild = bot_instance.guilds[0] if bot_instance.guilds else None
            if not guild:
                raise RuntimeError("沒有可用伺服器")

            channel = None
            if channel_id:
                channel = guild.get_channel(int(channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
            if not channel:
                raise RuntimeError("找不到可發送的文字頻道")

            if file_path:
                with open(file_path, 'rb') as f:
                    send_file = discord.File(f, filename=filename)
                    await channel.send(content=message or None, file=send_file)
            else:
                await channel.send(content=message or None)
            return {"message": f"已發送到頻道 {channel.mention}", "success": True}
        except Exception as e:
            print(f"❌ [WebPanel] 廣播發送失敗: {e}")
            return {"message": f"發送失敗: {e}", "success": False}

    result = asyncio.run_coroutine_threadsafe(do_broadcast(), loop_instance)
    try:
        result = result.result(timeout=120)
    except Exception as e:
        return jsonify({"message": f"發送超時或失敗: {e}", "success": False}), 500
    return jsonify(result)


# ============================================================
#  伺服器後台面板 (Server Admin Panel)
# ============================================================
@app.route('/server')
def server_panel():
    guild_id = request.args.get("guild")
    key = request.args.get("key")
    if not guild_id or not key:
        return "缺少參數", 400
    tokens = load_server_tokens()
    if tokens.get(str(guild_id)) != key:
        return "Unauthorized", 403
    return render_template_string(SERVER_HTML_TEMPLATE, guild_id=guild_id, key=key)

@app.route('/api/server/info')
def api_server_info():
    guild_id = request.args.get("guild")
    key = request.args.get("key")
    tokens = load_server_tokens()
    if tokens.get(str(guild_id)) != key:
        return jsonify({"error": "Unauthorized"}), 403
    if not bot_instance:
        return jsonify({"error": "Bot not ready"}), 500
    guild = bot_instance.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Guild not found"}), 404
    settings = bot_instance.get_cog("ManagementCog")  # not used, use config
    from utils.config import config_manager
    s = config_manager.get_guild_settings(guild.id)
    # 可管理模組與狀態
    modules = [
        {"key": "ai_enabled", "name": "🤖 AI 對話", "desc": "AI 聊天功能", "state": s.get("ai_enabled", True)},
        {"key": "music_enabled", "name": "🎵 音樂系統", "desc": "音樂播放", "state": s.get("music_enabled", True)},
        {"key": "economy_enabled", "name": "💰 經濟系統", "desc": "金幣/銀行/股市", "state": s.get("economy_enabled", True)},
        {"key": "security_enabled", "name": "🛡️ 安全防護", "desc": "掃毒/防廣告", "state": s.get("security_enabled", True)},
        {"key": "levels_enabled", "name": "📊 等級系統", "desc": "經驗值與排行", "state": s.get("levels_enabled", True)},
        {"key": "tickets_enabled", "name": "🎫 票單系統", "desc": "客服支援", "state": s.get("tickets_enabled", True)},
        {"key": "welcome_enabled", "name": "🌌 歡迎系統", "desc": "新成員歡迎", "state": s.get("welcome_enabled", True)},
        {"key": "games_enabled", "name": "🎮 小遊戲", "desc": "狼人殺/拉霸/賭博", "state": s.get("games_enabled", True)},
        {"key": "kuji_enabled", "name": "🏮 一番賞", "desc": "星空抽獎", "state": s.get("kuji_enabled", True)},
        {"key": "music_recc_enabled", "name": "🎧 音樂推薦", "desc": "智能推薦歌曲", "state": s.get("recommend_enabled", True)},
    ]
    return jsonify({
        "guild": {"name": guild.name, "id": str(guild.id), "members": guild.member_count,
                  "icon": guild.icon.url if guild.icon else None},
        "settings": s,
        "modules": modules
    })

@app.route('/api/server/toggle', methods=['POST'])
def api_server_toggle():
    data = request.get_json(silent=True) or request.form
    guild_id = data.get("guild")
    key = data.get("key")
    tokens = load_server_tokens()
    if tokens.get(str(guild_id)) != key:
        return jsonify({"error": "Unauthorized"}), 403
    module_key = data.get("module")
    new_state = data.get("enabled")
    if not module_key or new_state is None:
        return jsonify({"error": "Missing module/enabled"}), 400
    from utils.config import config_manager
    config_manager.set_guild_setting(int(guild_id), module_key, bool(new_state))
    return jsonify({"ok": True, "module": module_key, "enabled": bool(new_state)})

@app.route('/api/server/settings', methods=['POST'])
def api_server_settings():
    data = request.get_json(silent=True) or request.form
    guild_id = data.get("guild")
    key = data.get("key")
    tokens = load_server_tokens()
    if tokens.get(str(guild_id)) != key:
        return jsonify({"error": "Unauthorized"}), 403
    field = data.get("field")
    value = data.get("value")
    if not field or value is None:
        return jsonify({"error": "Missing field/value"}), 400
    from utils.config import config_manager
    # 簡單型別轉換
    try:
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif value.replace(".", "", 1).isdigit():
            value = float(value) if "." in value else int(value)
    except Exception:
        pass
    config_manager.set_guild_setting(int(guild_id), field, value)
    return jsonify({"ok": True, "field": field, "value": value})

@app.route('/api/widget/exchange', methods=['POST', 'OPTIONS'])
def api_widget_exchange():
    """接收 Worker 傳來的 authorization code，換成 access_token 並儲存"""
    if request.method == 'OPTIONS':
        resp = jsonify({"status": "ok"})
        resp.headers.add("Access-Control-Allow-Origin", "*")
        resp.headers.add("Access-Control-Allow-Headers", "Content-Type")
        resp.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return resp

    import requests as http_requests
    try:
        data = request.json
        code = data.get("code")
        if not code:
            resp = jsonify({"status": "error", "message": "Missing code"})
            resp.headers.add("Access-Control-Allow-Origin", "*")
            return resp, 400

        # 從 .env 讀取必要的 OAuth2 資訊
        client_id = None
        if bot_instance and bot_instance.application_id:
            client_id = str(bot_instance.application_id)
        if not client_id:
            # 從 token 解碼
            import base64
            token = os.getenv("DISCORD_TOKEN", "")
            first_part = token.split(".")[0]
            first_part += "=" * ((4 - len(first_part) % 4) % 4)
            client_id = base64.b64decode(first_part).decode("utf-8")

        client_secret = os.getenv("DISCORD_CLIENT_SECRET", "")
        if not client_secret:
            resp = jsonify({"status": "error", "message": "DISCORD_CLIENT_SECRET not set in .env"})
            resp.headers.add("Access-Control-Allow-Origin", "*")
            return resp, 500

        redirect_uri = "https://yokaro520.colacat878787.workers.dev"

        # 1. 用 code 換 access_token
        token_resp = http_requests.post("https://discord.com/api/v9/oauth2/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }, headers={
            "Content-Type": "application/x-www-form-urlencoded"
        })

        if token_resp.status_code != 200:
            print(f"❌ [Widget] Token 交換失敗: {token_resp.text}")
            resp = jsonify({"status": "error", "message": f"Token exchange failed: {token_resp.text}"})
            resp.headers.add("Access-Control-Allow-Origin", "*")
            return resp, 400

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        # 2. 用 access_token 取得 user ID
        user_resp = http_requests.get("https://discord.com/api/v9/users/@me", headers={
            "Authorization": f"Bearer {access_token}"
        })

        if user_resp.status_code != 200:
            print(f"❌ [Widget] 無法辨識用戶: {user_resp.text}")
            resp = jsonify({"status": "error", "message": "Failed to identify user"})
            resp.headers.add("Access-Control-Allow-Origin", "*")
            return resp, 400

        user_id = str(user_resp.json().get("id"))
        username = user_resp.json().get("username", "Unknown")

        # 3. 儲存 access_token
        db_path = "widget_users.json"
        db = {}
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    db = json.load(f)
            except: pass

        if user_id not in db:
            db[user_id] = {}
        db[user_id]["access_token"] = access_token

        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)

        print(f"✅ [Widget] 用戶 {username} ({user_id}) 的 OAuth2 Token 已成功儲存！")
        resp = jsonify({"status": "success", "username": username, "user_id": user_id})
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp

    except Exception as e:
        print(f"❌ [Widget] Code Exchange 失敗: {e}")
        import traceback
        traceback.print_exc()
        resp = jsonify({"status": "error", "message": str(e)})
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp, 500



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


    @commands.command(name='伺服器後台', aliases=['serverpanel', 'server_panel'])
    async def server_panel_cmd(self, ctx):
        """開啟本伺服器的管理後台 (僅限管理員)"""
        if not ctx.guild:
            return await ctx.send("❌ 請在伺服器內使用此指令。")
        if not ctx.author.guild_permissions.administrator and str(ctx.author.id) != "1113353915010920452":
            return await ctx.send("❌ 此功能僅限伺服器管理員使用。")

        domain = os.getenv("CUSTOM_DOMAIN")
        base_url = f"https://{domain}" if domain else self.tunnel_url
        if not base_url:
            base_url = f"http://localhost:{self.port}"

        token = get_server_token(ctx.guild.id)
        url = f"{base_url}/server?guild={ctx.guild.id}&key={token}"
        embed = discord.Embed(title="⚙️ 優卡洛 伺服器後台", color=0x2ecc71)
        embed.description = (
            f"您好，{ctx.author.mention}！\n\n"
            f"這是 **{ctx.guild.name}** 的管理後台連結：\n\n"
            f"🔗 **[點此開啟伺服器後台]({url})**\n\n"
            f"可在裡面管理優卡洛在貴伺服器內的功能開關與設定。"
        )
        embed.set_footer(text="僅限伺服器管理員使用")
        try:
            await ctx.author.send(embed=embed)
            await ctx.send("✅ 伺服器後台連結已發送到您的私訊！")
        except:
            await ctx.send(f"❌ 無法私訊您，請開啟私訊功能後再試。")

async def setup(bot):
    await bot.add_cog(WebPanelCog(bot))

