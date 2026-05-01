import discord
from discord.ext import commands
import asyncio
import os
import secrets
import threading
import json
from flask import Flask, render_template_string, request, jsonify
import psutil
from datetime import timedelta

app = Flask(__name__)
bot_instance = None
loop_instance = None

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
            --bg: #0b0e14;
            --card-bg: rgba(255, 255, 255, 0.03);
            --accent: #5865f2;
            --accent-glow: rgba(88, 101, 242, 0.4);
            --text-primary: #ffffff;
            --text-secondary: #949ba4;
            --danger: #ed4245;
        }
        * { box-sizing: border-box; }
        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg);
            color: var(--text-primary);
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            overflow-x: hidden;
            background-image: radial-gradient(circle at 50% -20%, #1e2129, #0b0e14);
        }
        .container {
            width: 100%;
            max-width: 1000px;
            padding: 40px 20px;
            display: grid;
            grid-template-columns: 1fr 350px;
            gap: 30px;
        }
        @media (max-width: 850px) { .container { grid-template-columns: 1fr; } }

        /* Player Card */
        .player-card {
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 24px;
            padding: 30px;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            position: relative;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        }
        .cover-art {
            width: 280px;
            height: 280px;
            border-radius: 20px;
            object-fit: cover;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            margin-bottom: 25px;
            transition: 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .cover-art.playing { transform: scale(1.05); }
        .track-info h1 { margin: 10px 0 5px; font-size: 24px; font-weight: 600; }
        .track-info p { margin: 0; color: var(--text-secondary); font-size: 16px; }
        
        /* Progress Bar */
        .progress-container { width: 100%; margin: 30px 0; }
        .progress-bar {
            width: 100%;
            height: 6px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            position: relative;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: var(--accent);
            width: 0%;
            box-shadow: 0 0 10px var(--accent-glow);
            transition: width 1s linear;
        }
        .time-info { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-secondary); margin-top: 8px; }

        /* Controls */
        .controls { display: flex; gap: 25px; align-items: center; }
        .btn {
            background: none;
            border: none;
            color: var(--text-primary);
            font-size: 24px;
            cursor: pointer;
            transition: 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 50px;
            height: 50px;
            border-radius: 50%;
        }
        .btn:hover { background: rgba(255,255,255,0.1); color: var(--accent); }
        .btn.play-pause {
            background: var(--accent);
            width: 65px;
            height: 65px;
            font-size: 28px;
            box-shadow: 0 0 20px var(--accent-glow);
        }
        .btn.play-pause:hover { transform: scale(1.1); background: #6772f1; }

        /* Queue Card */
        .queue-card {
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 24px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            max-height: 700px;
        }
        .section-header { font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
        .queue-list { overflow-y: auto; flex: 1; padding-right: 5px; }
        .queue-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            border-radius: 12px;
            margin-bottom: 8px;
            transition: 0.2s;
        }
        .queue-item:hover { background: rgba(255,255,255,0.05); }
        .queue-thumb { width: 45px; height: 45px; border-radius: 8px; object-fit: cover; }
        .queue-info { flex: 1; overflow: hidden; }
        .queue-title { font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .queue-author { font-size: 12px; color: var(--text-secondary); }

        /* Search Box */
        .search-box {
            position: relative;
            margin-bottom: 20px;
        }
        .search-box input {
            width: 100%;
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.1);
            color: white;
            padding: 12px 15px 12px 40px;
            border-radius: 12px;
            outline: none;
            transition: 0.3s;
        }
        .search-box input:focus { border-color: var(--accent); box-shadow: 0 0 10px var(--accent-glow); }
        .search-box i { position: absolute; left: 15px; top: 50%; transform: translateY(-50%); color: var(--text-secondary); }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="player-card">
            <div id="no-track" style="display:none; font-size:20px; color:var(--text-secondary)">目前沒有正在播放的音樂 💤</div>
            <div id="player-content">
                <img src="" alt="Cover" class="cover-art" id="track-cover">
                <div class="track-info">
                    <h1 id="track-title">載入中...</h1>
                    <p id="track-author">-</p>
                </div>
                <div class="progress-container">
                    <div class="progress-bar"><div class="progress-fill" id="prog-fill"></div></div>
                    <div class="time-info">
                        <span id="time-current">00:00</span>
                        <span id="time-total">00:00</span>
                    </div>
                </div>
                <div class="controls">
                    <button class="btn" onclick="control('prev')"><i class="fas fa-backward-step"></i></button>
                    <button class="btn play-pause" onclick="control('toggle')" id="play-btn"><i class="fas fa-pause"></i></button>
                    <button class="btn" onclick="control('skip')"><i class="fas fa-forward-step"></i></button>
                </div>
                <p style="margin-top:25px; font-size:12px; color:var(--text-secondary)" id="requester-info">點歌者: -</p>
            </div>
        </div>

        <div class="queue-card">
            <div class="section-header"><i class="fas fa-search"></i> 點歌系統</div>
            <div class="search-box">
                <i class="fas fa-search"></i>
                <input type="text" placeholder="搜尋歌曲或貼上網址..." id="search-input" onkeypress="if(event.key==='Enter') search()">
            </div>
            <div class="section-header"><i class="fas fa-list-ul"></i> 播放隊列 <span id="queue-count" style="margin-left:auto; background:var(--accent); padding:2px 8px; border-radius:20px; font-size:10px;">0</span></div>
            <div class="queue-list" id="queue-list">
                <!-- Queue items will be here -->
            </div>
        </div>
    </div>

    <script>
        const guildId = window.location.pathname.split('/').pop();
        let lastTitle = '';

        async function api(path, method='GET', body=null) {
            const opts = { method };
            if(body) { opts.headers = {'Content-Type': 'application/json'}; opts.body = JSON.stringify(body); }
            const res = await fetch(`/api/music/${guildId}\${path}`, opts);
            return res.json();
        }

        async function update() {
            const data = await api('/status');
            if(data.error || !data.playing) {
                document.getElementById('no-track').style.display = 'block';
                document.getElementById('player-content').style.display = 'none';
                document.getElementById('queue-list').innerHTML = '';
                return;
            }
            document.getElementById('no-track').style.display = 'none';
            document.getElementById('player-content').style.display = 'block';

            const track = data.track;
            document.getElementById('track-title').innerText = track.title;
            document.getElementById('track-author').innerText = track.author || 'YouTube';
            document.getElementById('track-cover').src = track.thumbnail;
            document.getElementById('time-total').innerText = track.duration_str;
            document.getElementById('time-current').innerText = data.position_str;
            document.getElementById('prog-fill').style.width = data.progress + '%';
            document.getElementById('requester-info').innerText = '點歌者: ' + (track.requester || '系統');
            document.getElementById('play-btn').innerHTML = data.is_paused ? '<i class="fas fa-play"></i>' : '<i class="fas fa-pause"></i>';
            document.getElementById('track-cover').className = data.is_paused ? 'cover-art' : 'cover-art playing';

            // Queue
            const qList = document.getElementById('queue-list');
            document.getElementById('queue-count').innerText = data.queue.length;
            qList.innerHTML = '';
            data.queue.forEach(item => {
                qList.innerHTML += `
                    <div class="queue-item">
                        <img src="\${item.thumbnail}" class="queue-thumb">
                        <div class="queue-info">
                            <div class="queue-title">\${item.title}</div>
                            <div class="queue-author">\${item.duration_str}</div>
                        </div>
                    </div>
                `;
            });
        }

        async function control(action) { await api('/control', 'POST', {action}); update(); }
        async function search() {
            const input = document.getElementById('search-input');
            const q = input.value; if(!q) return;
            input.value = '正在點歌...'; input.disabled = true;
            await api('/add', 'POST', {query: q});
            input.value = ''; input.disabled = false;
            update();
        }

        setInterval(update, 2000);
        update();
    </script>
</body>
</html>
"""

# --- API 路由 ---
@app.route("/music/<guild_id>")
def music_index(guild_id):
    return render_template_string(MUSIC_HTML_TEMPLATE)

@app.route("/api/music/<guild_id>/status")
def music_status(guild_id):
    music_cog = bot_instance.get_cog("MusicCog")
    if not music_cog: return jsonify({"error": "Music module not loaded"})
    
    gid = int(guild_id)
    vc = None
    for guild in bot_instance.guilds:
        if guild.id == gid:
            vc = guild.voice_client
            break
            
    if not vc or not vc.source:
        return jsonify({"playing": False, "queue": []})
        
    source = vc.source
    # 處理可能的播放器進度
    elapsed = time.time() - source.start_time
    progress = (elapsed / source.duration) * 100 if source.duration > 0 else 0
    
    queue = music_cog.queue.get(gid, [])
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
        "position_str": str(timedelta(seconds=int(elapsed))),
        "progress": min(100, progress),
        "track": {
            "title": source.title,
            "thumbnail": source.thumbnail,
            "duration": source.duration,
            "duration_str": str(timedelta(seconds=source.duration)),
            "requester": source.requester.display_name if source.requester else "Unknown"
        },
        "queue": q_data
    })

@app.route("/api/music/<guild_id>/control", methods=['POST'])
def music_control(guild_id):
    data = request.json
    action = data.get('action')
    gid = int(guild_id)
    
    async def do_control():
        vc = None
        for guild in bot_instance.guilds:
            if guild.id == gid:
                vc = guild.voice_client
                break
        if not vc: return
        
        if action == 'toggle':
            if vc.is_paused(): vc.resume()
            else: vc.pause()
        elif action == 'skip':
            vc.stop()
            
    asyncio.run_coroutine_threadsafe(do_control(), loop_instance)
    return jsonify({"status": "ok"})

@app.route("/api/music/<guild_id>/add", methods=['POST'])
def music_add(guild_id):
    data = request.json
    query = data.get('query')
    gid = int(guild_id)
    
    async def do_add():
        music_cog = bot_instance.get_cog("MusicCog")
        guild = bot_instance.get_guild(gid)
        if not music_cog or not guild: return
        
        # 這裡需要模擬一個 ctx
        class MockCtx:
            def __init__(self, guild, bot):
                self.guild = guild
                self.author = bot.user # 以機器人身分點歌
                self.bot = bot
            async def send(self, *args, **kwargs): pass
            
        ctx = MockCtx(guild, bot_instance)
        # 呼叫 MusicCog 的播放邏輯 (假設指令名稱是 play)
        cmd = music_cog.play
        await cmd(music_cog, ctx, search=query)
        
    asyncio.run_coroutine_threadsafe(do_add(), loop_instance)
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
