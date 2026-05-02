import discord
from discord.ext import commands
import asyncio
import os
import secrets
import threading
import json
from flask import render_template_string, jsonify, request
from cogs.webpanel import app, bot_instance, loop_instance
from datetime import timedelta
import time

# --- 音樂儀表板 HTML 模板 ---
MUSIC_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yokaro Music | 線上音樂廳</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root {
            --bg: #05070a;
            --card-bg: rgba(20, 24, 35, 0.6);
            --accent: #7289da;
            --accent-glow: rgba(114, 137, 218, 0.4);
            --text-primary: #ffffff;
            --text-secondary: #aeb5bd;
            --danger: #ff4757;
            --success: #2ed573;
        }
        * { box-sizing: border-box; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg);
            color: var(--text-primary);
            margin: 0;
            display: flex;
            justify-content: center;
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 10% 10%, rgba(114, 137, 218, 0.05), transparent 30%),
                radial-gradient(circle at 90% 90%, rgba(255, 71, 87, 0.05), transparent 30%);
            overflow-x: hidden;
        }
        .container {
            width: 100%;
            max-width: 1100px;
            padding: 40px 20px;
            display: grid;
            grid-template-columns: 1fr 380px;
            gap: 30px;
        }
        @media (max-width: 950px) { .container { grid-template-columns: 1fr; } }

        /* Glass Panel Base */
        .glass-panel {
            background: var(--card-bg);
            backdrop-filter: blur(25px) saturate(180%);
            -webkit-backdrop-filter: blur(25px) saturate(180%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 32px;
            box-shadow: 0 30px 60px rgba(0,0,0,0.4);
        }

        /* Player Main Card */
        .player-card {
            padding: 40px;
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
        }
        .cover-wrapper {
            position: relative;
            margin-bottom: 30px;
        }
        .cover-wrapper::after {
            content: '';
            position: absolute;
            top: 15px; left: 15px; right: 15px; bottom: 15px;
            background: inherit;
            filter: blur(40px);
            opacity: 0.6;
            z-index: -1;
        }
        .cover-art {
            width: 320px;
            height: 320px;
            border-radius: 28px;
            object-fit: cover;
            box-shadow: 0 15px 45px rgba(0,0,0,0.6);
        }
        .cover-art.playing { animation: pulse 4s infinite ease-in-out; }
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.03); }
        }

        .track-info h1 { font-size: 28px; font-weight: 800; margin: 15px 0 8px; letter-spacing: -0.5px; text-align: center; }
        .track-info p { color: var(--text-secondary); font-size: 18px; margin: 0; text-align: center; }
        
        .progress-container { width: 100%; margin: 35px 0 20px; }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            cursor: pointer;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent), #9ba8e9);
            width: 0%;
            border-radius: 20px;
            box-shadow: 0 0 15px var(--accent-glow);
        }
        .time-labels { display: flex; justify-content: space-between; margin-top: 12px; font-size: 13px; font-weight: 600; color: var(--text-secondary); }

        .main-controls { display: flex; gap: 30px; align-items: center; }
        .control-btn {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.05);
            color: white;
            width: 55px; height: 55px;
            border-radius: 50%;
            font-size: 20px;
            cursor: pointer;
            display: flex; align-items: center; justify-content: center;
        }
        .control-btn:hover { background: rgba(255,255,255,0.1); transform: translateY(-3px); color: var(--accent); }
        .play-pause-btn {
            width: 75px; height: 75px;
            background: var(--accent);
            font-size: 28px;
            box-shadow: 0 10px 25px var(--accent-glow);
        }
        .play-pause-btn:hover { transform: scale(1.1); box-shadow: 0 15px 35px var(--accent-glow); }

        /* Sidebar Cards */
        .sidebar-section { padding: 25px; margin-bottom: 20px; }
        .section-title {
            font-size: 14px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-secondary);
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .input-group { position: relative; margin-bottom: 25px; }
        .input-group i { position: absolute; left: 18px; top: 50%; transform: translateY(-50%); color: var(--text-secondary); }
        .input-group input, .input-group select {
            width: 100%;
            background: rgba(0,0,0,0.25);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 14px 15px 14px 45px;
            color: white;
            outline: none;
            font-size: 14px;
        }
        .input-group input:focus, .input-group select:focus { border-color: var(--accent); background: rgba(0,0,0,0.4); }

        .action-btn {
            width: 100%;
            padding: 14px;
            border-radius: 16px;
            border: none;
            font-weight: 700;
            cursor: pointer;
            display: flex; align-items: center; justify-content: center; gap: 10px;
            margin-bottom: 10px;
        }
        .btn-primary { background: var(--accent); color: white; }
        .btn-danger { background: rgba(255, 71, 87, 0.15); color: var(--danger); border: 1px solid rgba(255, 71, 87, 0.2); }
        .btn-danger:hover { background: var(--danger); color: white; }

        .queue-list { overflow-y: auto; max-height: 400px; padding-right: 5px; }
        .queue-item {
            display: flex; align-items: center; gap: 15px; padding: 12px;
            border-radius: 18px; margin-bottom: 10px;
            background: rgba(255,255,255,0.02);
        }
        .queue-item:hover { background: rgba(255,255,255,0.05); }
        .queue-thumb { width: 50px; height: 50px; border-radius: 12px; object-fit: cover; }
        .queue-meta { flex: 1; overflow: hidden; }
        .queue-name { font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .queue-dur { font-size: 12px; color: var(--text-secondary); }

        #no-track { text-align: center; padding: 100px 0; }
        #no-track i { font-size: 60px; color: var(--accent); opacity: 0.3; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Main Player -->
        <div class="glass-panel player-card">
            <div id="no-track" style="display:none;">
                <i class="fas fa-compact-disc fa-spin"></i>
                <h2 style="color:var(--text-secondary)">優卡洛正在待機中...</h2>
                <p style="color:var(--text-secondary)">點擊右側來放首歌吧！</p>
            </div>
            <div id="player-content" style="width:100%; display:flex; flex-direction:column; align-items:center;">
                <div class="cover-wrapper">
                    <img src="" alt="Cover" class="cover-art" id="track-cover">
                </div>
                <div class="track-info">
                    <h1 id="track-title">載入中...</h1>
                    <p id="track-author">-</p>
                </div>
                
                <div class="progress-container">
                    <div class="progress-bar"><div class="progress-fill" id="prog-fill"></div></div>
                    <div class="time-labels">
                        <span id="time-current">00:00</span>
                        <span id="time-total">00:00</span>
                    </div>
                </div>

                <div class="main-controls">
                    <button class="control-btn" onclick="control('prev')"><i class="fas fa-backward"></i></button>
                    <button class="control-btn play-pause-btn" onclick="control('toggle')" id="play-btn"><i class="fas fa-pause"></i></button>
                    <button class="control-btn" onclick="control('skip')"><i class="fas fa-forward"></i></button>
                </div>
                
                <div style="margin-top:40px; display:flex; align-items:center; gap:10px; padding:10px 20px; border-radius:50px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05);">
                    <i class="fas fa-user-circle" style="color:var(--accent)"></i>
                    <span id="requester-info" style="font-size:12px; font-weight:600; color:var(--text-secondary)">點歌者: -</span>
                </div>
            </div>
        </div>

        <!-- Sidebar -->
        <div class="sidebar">
            <!-- Voice Control -->
            <div class="glass-panel sidebar-section">
                <div class="section-title"><i class="fas fa-signal"></i> 語音通訊</div>
                <div class="input-group">
                    <i class="fas fa-microphone-lines"></i>
                    <select id="vc-select">
                        <option value="">載入頻道中...</option>
                    </select>
                </div>
                <button class="action-btn btn-primary" onclick="joinChannel()"><i class="fas fa-sign-in-alt"></i> 進入頻道</button>
                <button class="action-btn btn-danger" onclick="control('stop')"><i class="fas fa-power-off"></i> 斷開連接</button>
                
                <hr style="border:0; border-top:1px solid rgba(255,255,255,0.05); margin:20px 0;">
                
                <div class="section-title"><i class="fas fa-broadcast-tower"></i> 雲端廣播 (TTS)</div>
                <div class="input-group">
                    <i class="fas fa-comment-dots"></i>
                    <input type="text" id="tts-input" placeholder="輸入要廣播的文字...">
                </div>
                <button class="action-btn btn-primary" onclick="sendTTS()"><i class="fas fa-paper-plane"></i> 發送語音</button>
                
                <hr style="border:0; border-top:1px solid rgba(255,255,255,0.05); margin:20px 0;">
                
                <div class="section-title"><i class="fas fa-ear-listen"></i> 即時監聽</div>
                <button class="action-btn" id="monitor-btn" onclick="toggleMonitor()" style="background:rgba(255,255,255,0.05); color:white;">
                    <i class="fas fa-volume-high"></i> <span>開啟監聽</span>
                </button>
                <audio id="voice-monitor" style="display:none;"></audio>
            </div>

            <!-- Search & Queue -->
            <div class="glass-panel sidebar-section" style="flex:1">
                <div class="section-title"><i class="fas fa-search"></i> 音樂搜尋</div>
                <div class="input-group">
                    <i class="fas fa-music"></i>
                    <input type="text" placeholder="輸入關鍵字按下 Enter..." id="search-input" onkeypress="if(event.key==='Enter') search()">
                </div>
                
                <!-- 搜尋結果預覽區 -->
                <div id="search-results" style="display:none; margin-bottom:20px; padding:10px; background:rgba(0,0,0,0.2); border-radius:16px; border:1px solid rgba(255,255,255,0.05);">
                    <div class="section-title" style="font-size:12px;"><i class="fas fa-list-check"></i> 請選擇歌曲</div>
                    <div id="results-list"></div>
                    <button class="action-btn btn-danger" style="margin-top:10px; padding:8px; font-size:12px;" onclick="closeSearch()">取消搜尋</button>
                </div>
        </div>
    </div>

    <script>
        const guildId = window.location.pathname.split('/').pop();
        let localPos = 0; let totalDur = 0; let isPaused = true;

        async function api(path, method='GET', body=null) {
            const opts = { method };
            if(body) { opts.headers = {'Content-Type': 'application/json'}; opts.body = JSON.stringify(body); }
            const res = await fetch(`/api/music/${guildId}${path}`, opts);
            return res.json();
        }

        function formatTime(secs) {
            const d = new Date(secs * 1000);
            const m = d.getUTCMinutes(); const s = d.getUTCSeconds();
            return `${m}:${s.toString().padStart(2,'0')}`;
        }

        async function update() {
            const data = await api('/status');
            if(!data.playing) {
                document.getElementById('no-track').style.display = 'block';
                document.getElementById('player-content').style.display = 'none';
            } else {
                document.getElementById('no-track').style.display = 'none';
                document.getElementById('player-content').style.display = 'flex';
                const track = data.track;
                document.getElementById('track-title').innerText = track.title;
                document.getElementById('track-author').innerText = track.author;
                document.getElementById('track-cover').src = track.thumbnail;
                document.getElementById('time-total').innerText = track.duration_str;
                document.getElementById('requester-info').innerText = '點歌者: ' + track.requester;
                document.getElementById('play-btn').innerHTML = data.is_paused ? '<i class="fas fa-play"></i>' : '<i class="fas fa-pause"></i>';
                document.getElementById('track-cover').className = data.is_paused ? 'cover-art' : 'cover-art playing';
                localPos = data.position; totalDur = track.duration; isPaused = data.is_paused;
            }

            // Queue
            const qList = document.getElementById('queue-list');
            document.getElementById('queue-count').innerText = data.queue.length;
            qList.innerHTML = '';
            data.queue.forEach(item => {
                qList.innerHTML += `
                    <div class="queue-item">
                        <img src="${item.thumbnail}" class="queue-thumb">
                        <div class="queue-meta">
                            <div class="queue-name">${item.title}</div>
                            <div class="queue-dur">${item.duration_str}</div>
                        </div>
                    </div>
                `;
            });
        }

        async function loadChannels() {
            const data = await api('/channels');
            const select = document.getElementById('vc-select');
            select.innerHTML = '';
            data.channels.forEach(ch => {
                const opt = document.createElement('option');
                opt.value = ch.id; opt.innerText = (ch.current ? '🔊 ' : '') + ch.name;
                if(ch.current) opt.selected = true;
                select.appendChild(opt);
            });
        }

        async function joinChannel() {
            const chId = document.getElementById('vc-select').value;
            if(!chId) return;
            await api('/join', 'POST', {channel_id: chId});
            setTimeout(loadChannels, 1000);
        }

        async function leaveChannel() {
            if(!confirm('確定要讓優卡洛離開語音頻道嗎？')) return;
            await api('/leave', 'POST');
            setTimeout(loadChannels, 1000);
            update();
        }

        setInterval(() => {
            if(!isPaused && localPos < totalDur) {
                localPos += 1;
                document.getElementById('time-current').innerText = formatTime(localPos);
                document.getElementById('prog-fill').style.width = (localPos / totalDur * 100) + '%';
            }
        }, 1000);

        async function sendTTS() {
            const input = document.getElementById('tts-input');
            const text = input.value;
            if(!text) return;
            input.value = '正在發送...';
            await api('/tts', 'POST', {text: text});
            input.value = '';
        }

        let isMonitoring = false;
        function toggleMonitor() {
            const btn = document.getElementById('monitor-btn');
            const audio = document.getElementById('voice-monitor');
            const span = btn.querySelector('span');
            const icon = btn.querySelector('i');

            if(!isMonitoring) {
                audio.src = `/api/music/${guildId}/listen?t=${Date.now()}`;
                audio.play();
                span.innerText = '停止監聽';
                btn.style.background = 'var(--danger)';
                icon.className = 'fas fa-stop-circle';
                isMonitoring = true;
            } else {
                audio.pause();
                audio.src = '';
                span.innerText = '開啟監聽';
                btn.style.background = 'rgba(255,255,255,0.05)';
                icon.className = 'fas fa-volume-high';
                isMonitoring = false;
            }
        }

        async function control(action) { await api('/control', 'POST', {action}); update(); }
        
        async function search() {
            // ... (保持搜尋邏輯)
            const input = document.getElementById('search-input');
            const q = input.value; if(!q) return;
            input.value = '正在搜尋...'; input.disabled = true;
            
            const data = await api(`/search?q=${encodeURIComponent(q)}`);
            input.value = ''; input.disabled = false;
            
            if(data.results && data.results.length > 0) {
                const resDiv = document.getElementById('search-results');
                const listDiv = document.getElementById('results-list');
                listDiv.innerHTML = '';
                data.results.forEach(item => {
                    listDiv.innerHTML += `
                        <div class="queue-item" style="cursor:pointer; background:rgba(255,255,255,0.03);" onclick="selectSong('${item.url}')">
                            <img src="${item.thumbnail}" class="queue-thumb">
                            <div class="queue-meta">
                                <div class="queue-name">${item.title}</div>
                                <div class="queue-dur">${item.author} • ${item.duration}</div>
                            </div>
                        </div>
                    `;
                });
                resDiv.style.display = 'block';
            } else {
                alert('找不到相關歌曲 😰');
            }
        }

        async function selectSong(url) {
            document.getElementById('search-results').style.display = 'none';
            await api('/add', 'POST', {url: url});
            update();
        }

        function closeSearch() {
            document.getElementById('search-results').style.display = 'none';
        }

        setInterval(update, 5000); update(); loadChannels();
    </script>
</body>
</html>
"""

# --- API 路由 ---
@app.route("/music/<int:guild_id>")
def music_index(guild_id):
    return render_template_string(MUSIC_HTML_TEMPLATE, guild_id=guild_id)

@app.route("/api/music/<int:guild_id>/status")
def music_status(guild_id):
    music_cog = bot_instance.get_cog("MusicCog")
    if not music_cog: return jsonify({"error": "Music module not loaded"})
    
    guild = bot_instance.get_guild(guild_id)
    if not guild or not guild.voice_client or not guild.voice_client.source:
        return jsonify({"playing": False, "queue": []})
        
    vc = guild.voice_client
    source = vc.source
    elapsed = time.time() - source.start_time
    
    queue = music_cog.queue.get(guild_id, [])
    q_data = []
    for item in queue[:20]:
        q_data.append({
            "title": item.get('title', 'Unknown'),
            "thumbnail": item.get('thumbnail', ''),
            "duration_str": str(timedelta(seconds=item.get('duration', 0)))
        })
        
    return jsonify({
        "playing": True,
        "is_paused": vc.is_paused(),
        "position": elapsed,
        "track": {
            "title": source.title,
            "author": source.data.get('uploader', 'Unknown'),
            "thumbnail": source.thumbnail,
            "duration": source.duration,
            "duration_str": str(timedelta(seconds=source.duration)),
            "requester": source.requester.display_name if source.requester else "Unknown"
        },
        "queue": q_data
    })

@app.route("/api/music/<int:guild_id>/control", methods=['POST'])
def music_control(guild_id):
    data = request.json
    action = data.get('action')
    guild = bot_instance.get_guild(guild_id)
    if not guild or not guild.voice_client: return jsonify({"status": "no vc"})
    
    vc = guild.voice_client
    async def do_control():
        if action == 'toggle':
            if vc.is_paused(): vc.resume()
            else: vc.pause()
        elif action == 'skip': vc.stop()
            
    asyncio.run_coroutine_threadsafe(do_control(), loop_instance)
    return jsonify({"status": "ok"})

@app.route("/api/music/<int:guild_id>/leave", methods=['POST'])
def music_leave(guild_id):
    guild = bot_instance.get_guild(guild_id)
    if guild and guild.voice_client:
        asyncio.run_coroutine_threadsafe(guild.voice_client.disconnect(), loop_instance)
    return jsonify({"status": "ok"})

@app.route("/api/music/<int:guild_id>/search")
def music_search(guild_id):
    query = request.args.get('q')
    if not query: return jsonify({"results": []})
    
    # 使用 yt-dlp 進行搜尋 (獲取前 5 個結果)
    import yt_dlp
    YDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch5'}
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            results = []
            for entry in info.get('entries', []):
                results.append({
                    "title": entry.get('title'),
                    "url": entry.get('webpage_url'),
                    "thumbnail": entry.get('thumbnail'),
                    "duration": str(timedelta(seconds=entry.get('duration', 0))),
                    "author": entry.get('uploader')
                })
            return jsonify({"results": results})
        except Exception as e:
            return jsonify({"error": str(e), "results": []})

@app.route("/api/music/<int:guild_id>/add", methods=['POST'])
def music_add(guild_id):
    data = request.json
    url = data.get('url')
    guild = bot_instance.get_guild(guild_id)
    music_cog = bot_instance.get_cog("MusicCog")
    
    if not guild or not music_cog: return jsonify({"error": "Not found"}), 404
    
    async def do_add():
        # 建立一個具有語音狀態的 Mock 帳號
        author = guild.me
        if guild.voice_client and guild.voice_client.channel.members:
            humans = [m for m in guild.voice_client.channel.members if not m.bot]
            if humans: author = humans[0]

        # 模擬 VoiceState
        class MockVoiceState:
            def __init__(self, channel):
                self.channel = channel

        # 模擬 AsyncContextManager for ctx.typing()
        class MockTyping:
            async def __aenter__(self): pass
            async def __aexit__(self, exc_type, exc_val, exc_tb): pass

        class MockCtx:
            def __init__(self, guild, author, bot):
                self.guild = guild
                self.author = author
                self.bot = bot
                self.voice_client = guild.voice_client
                self.channel = guild.text_channels[0] if guild.text_channels else None
                self.message = None # 雖然是 None，但屬性必須存在
                # 關鍵：模擬語音狀態
                self.author.voice = MockVoiceState(guild.voice_client.channel) if guild.voice_client else None
            
            def typing(self): return MockTyping()
            async def send(self, *args, **kwargs): 
                content = args[0] if args else kwargs.get('content', '')
                print(f"🎵 [WebMusic] {content}")
                # 模擬回傳一個消息對象
                class MockMsg:
                    def __init__(self): self.id = 0
                    async def delete(self): pass
                    async def edit(self, *args, **kwargs): pass
                return MockMsg()
            
        ctx = MockCtx(guild, author, bot_instance)
        
        try:
            print(f"🛰️ [WebMusic] 正在點歌: {url}")
            # 直接抓取 MusicCog 的 play 函數對象
            play_cmd = music_cog.play
            if hasattr(play_cmd, 'callback'): play_cmd = play_cmd.callback
            
            # 執行播放
            await play_cmd(music_cog, ctx, search=url)
            
            # 如果還是沒唱，檢查隊列並強啟
            await asyncio.sleep(2)
            if guild.voice_client and not guild.voice_client.is_playing():
                print("⚡ [WebMusic] 偵測到閒置，嘗試手動觸發隊列...")
                # 這裡如果 play 指令沒帶 search 參數會播放下一首 (視 music.py 邏輯而定)
                await play_cmd(music_cog, ctx, search=None)
        except Exception as e:
            import traceback
            print(f"❌ [WebMusic] 致命錯誤: {e}")
            traceback.print_exc()
        
    @app.route("/api/music/<int:guild_id>/tts", methods=['POST'])
    def music_tts(guild_id):
        data = request.json
        text = data.get("text")
        if not text: return jsonify({"error": "No text"}), 400
        
        music_cog = bot_instance.get_cog("MusicCog")
        guild = bot_instance.get_guild(guild_id)
        if not music_cog or not guild: return jsonify({"error": "Not found"}), 404
        
        async def do_tts():
            # 這裡我們模擬一個播放，或是調用 tts_cog (如果有的話)
            # 簡單起見，我們先用播放器播放 TTS 的音訊流
            # 您可以之後擴充成調用特定的 TTS 模組
            print(f"📣 [WebTTS] 正在廣播: {text}")
            # 這裡假設您的 MusicCog 有一個 play_tts 或是類似功能的邏輯
            # 我們直接使用 discord.py 的 VoiceClient 播放
            if guild.voice_client:
                # 這裡調用您現有的 TTS 產生邏輯 (例如 gTTS)
                from gtts import gTTS
                import io
                tts = gTTS(text=text, lang='zh-tw')
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)
                source = discord.FFmpegPCMAudio(fp, pipe=True)
                if guild.voice_client.is_playing(): guild.voice_client.stop()
                guild.voice_client.play(source)
                
        asyncio.run_coroutine_threadsafe(do_tts(), loop_instance)
        return jsonify({"status": "ok"})

    @app.route("/api/music/<int:guild_id>/listen")
    def music_listen(guild_id):
        # 即時監聽流 (Audio Stream)
        def generate_voice():
            guild = bot_instance.get_guild(guild_id)
            if not guild or not guild.voice_client: return
            while True:
                yield b'\x00' * 1600 # 靜音占位 (後續可擴充實時數據)
                time.sleep(0.02)
        return Response(generate_voice(), mimetype="audio/wav")

    @app.route("/api/music/<int:guild_id>/channels")
    def music_channels(guild_id):
        guild = bot_instance.get_guild(guild_id)
        if not guild: return jsonify({"channels": []})
        channels = [{"id": str(c.id), "name": c.name} for c in guild.voice_channels]
        return jsonify({"channels": channels})
        # 即時監聽流 (Audio Stream)
        def generate_voice():
            guild = bot_instance.get_guild(guild_id)
            if not guild or not guild.voice_client: return
            
            # 這裡我們需要從 record.py 或 voice_recv 獲取 PCM 數據
            # 簡單起見，我們先回傳一個「正在嘗試連線」的提示或是靜音流
            # 真正的實作需要對接 voice_recv 的 sink
            while True:
                # 模擬獲取 20ms 的數據
                yield b'\x00' * 1600 # 靜音占位
                time.sleep(0.02)

        return Response(generate_voice(), mimetype="audio/wav")
    guild = bot_instance.get_guild(guild_id)
    if not guild: return jsonify({"channels": []})
    
    channels = []
    for vc in guild.voice_channels:
        channels.append({
            "id": str(vc.id),
            "name": vc.name,
            "current": guild.voice_client and guild.voice_client.channel.id == vc.id
        })
    return jsonify({"channels": channels})

@app.route("/api/music/<int:guild_id>/join", methods=['POST'])
def music_join(guild_id):
    data = request.json
    channel_id = int(data.get("channel_id"))
    guild = bot_instance.get_guild(guild_id)
    channel = bot_instance.get_channel(channel_id)
    
    if not guild or not channel: return jsonify({"error": "Not found"}), 404
    
    async def do_join():
        if guild.voice_client: await guild.voice_client.move_to(channel)
        else: await channel.connect()
            
    asyncio.run_coroutine_threadsafe(do_join(), loop_instance)
    return jsonify({"status": "ok"})

class MusicWebPanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        global bot_instance, loop_instance
        bot_instance = bot
        loop_instance = bot.loop
        
    @commands.command(name='musiclink')
    async def music_link(self, ctx):
        # 獲取 WebPanel 的隧道網址
        web_cog = self.bot.get_cog("WebPanelCog")
        if not web_cog or not web_cog.tunnel_url:
            return await ctx.send("❌ WebPanel 隧道未啟動，無法獲取連結。")
            
        url = f"{web_cog.tunnel_url}/music/{ctx.guild.id}"
        embed = discord.Embed(title="🎵 Yokaro 線上音樂儀表板", color=0x5865f2)
        embed.description = f"點擊下方連結即可進入專屬音樂廳，即時控制、點歌與查看歌單！\n\n🔗 **[進入音樂廳]({url})**"
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MusicWebPanelCog(bot))
