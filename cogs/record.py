import discord
from discord.ext import commands
print("🚀 [DEBUG] record.py 文件正在被 Python 讀取中...")
import asyncio
import os
import time
import subprocess
import json
import shutil
from concurrent.futures import ThreadPoolExecutor

# 注意：我們需要 discord-ext-voice-recv 插件
try:
    import discord.ext.voice_recv as voice_recv
    HAS_VOICE_RECV = True
    print("💠 [錄影機] 語音接收模組載入成功！")
except ImportError as e:
    HAS_VOICE_RECV = False
    print(f"⚠️ [錄影機] 語音接收模組載入失敗: {e}")

class AudioBuffer:
    def __init__(self, user, folder):
        self.user = user
        self.folder = folder
        self.file_path = f"{folder}/user_{user.id}.pcm"
        self.file = open(self.file_path, "wb")
        self.start_time = time.time()

    def write(self, data):
        self.file.write(data)

    def close(self):
        self.file.close()

class SyncedAudioSink(voice_recv.AudioSink):
    def __init__(self, folder):
        super().__init__()
        self.folder = folder
        self.buffers = {}
        self.start_time = time.time()

    def wants_opus(self):
        return False # 我們要 PCM 資料

    def write(self, user, data):
        # 增加異常保護，過濾掉損壞的包
        try:
            if not data or not data.pcm: return
            
            if user not in self.buffers:
                self.buffers[user] = AudioBuffer(user, self.folder)
            
            self.buffers[user].write(data.pcm)
        except Exception as e:
            print(f"Sink Write Error (User {user}): {e}")

    def cleanup(self):
        for buffer in self.buffers.values():
            buffer.close()

class RecordCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.recordings = {} # guild_id: SyncedAudioSink
        self.executor = ThreadPoolExecutor(max_workers=2)

    @commands.group(name='record', aliases=['錄音', '錄影'], invoke_without_command=True)
    async def record_group(self, ctx):
        """!record start/stop - 錄製語音頻道並自動生成字幕影片"""
        await ctx.send("❓ 請使用 `!record start` 或 `!record stop` 來控制錄影機喔！")

    @record_group.command(name='start')
    async def record_start(self, ctx):
        """開始錄製當前語音頻道"""
        if not HAS_VOICE_RECV:
            return await ctx.send("❌ 伺服器尚未安裝 `discord-ext-voice-recv` 模組，請稍候重啟！")

        if not ctx.author.voice:
            return await ctx.send("嗷～你沒在語音頻道耶！")

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                await ctx.voice_client.move_to(ctx.author.voice.channel)
        else:
            try:
                await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
            except Exception as e:
                return await ctx.send(f"❌ 語音連線失敗: {e}")

        # 建立錄音資料匣
        rec_id = int(time.time())
        folder = f"temp/rec_{rec_id}"
        os.makedirs(folder, exist_ok=True)

        sink = SyncedAudioSink(folder)
        self.recordings[ctx.guild.id] = sink
        
        try:
            ctx.voice_client.listen(sink)
            embed = discord.Embed(title="🎙️ 洛洛錄影機：影視級開拍！", color=0xff0000)
            embed.description = "正在錄製中... 結束後我會自動剪輯影片並上字幕。\n📢 **重要：請確保已取得所有成員同意錄製！**"
            embed.set_footer(text="輸入 !record stop 結束錄製")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ 啟動收音機失敗: {e}")

    @record_group.command(name='stop')
    async def record_stop(self, ctx):
        """停止錄製並開始【AI 自動剪輯】"""
        if ctx.guild.id not in self.recordings:
            return await ctx.send("❓ 洛洛目前沒有在錄影喔！")

        sink = self.recordings.pop(ctx.guild.id)
        if ctx.voice_client:
            ctx.voice_client.stop_listening()
        
        sink.cleanup()
        msg = await ctx.send("🎬 正在啟動【影視級 AI 剪輯模組】... 請稍候，洛洛正在努力畫圖中！🐾")

        # 開啟異步處理
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(self.executor, self._process_render_sync, sink)
        asyncio.create_task(self._wait_and_send(ctx, future, msg))

    async def _wait_and_send(self, ctx, future, status_msg):
        try:
            video_path = await future
            if video_path and os.path.exists(video_path):
                await status_msg.edit(content="🎉 剪輯完成！正在傳送影片... 嗷嗚！")
                await ctx.send(file=discord.File(video_path))
                # 傳送完理一下空間
                shutil.rmtree(os.path.dirname(video_path), ignore_errors=True)
            else:
                await status_msg.edit(content="❌ 哎呀，影片合成時發生意外了！請檢查控制台 Log。")
        except Exception as e:
            await status_msg.edit(content=f"❌ 剪輯失敗: {e}")

    def _process_render_sync(self, sink):
        """同步處理：混音 -> 辨識 -> 渲染"""
        try:
            folder = sink.folder
            if not sink.buffers: return None

            print(f"[Record] 正在準備渲染素材 (頭像與音軌)...")
            
            # 1. 下載頭像
            import requests
            avatar_paths = {}
            for user in sink.buffers.keys():
                try:
                    p = f"{folder}/avatar_{user.id}.png"
                    res = requests.get(user.display_avatar.url, timeout=10)
                    with open(p, "wb") as f: f.write(res.content)
                    avatar_paths[user.id] = p
                except Exception as e:
                    print(f"下載頭像失敗 ({user.id}): {e}")

            mixed_wav = f"{folder}/mixed.wav"
            # 指向第一個有效的 PCM
            first_user_pcm = list(sink.buffers.values())[0].file_path
            
            subprocess.run([
                "ffmpeg", "-y", "-f", "s16le", "-ar", "48000", "-ac", "2", 
                "-i", first_user_pcm, mixed_wav
            ], check=True, capture_output=True)

            # 2. AI 辨識 (Faster-Whisper)
            print("[Record] 正在執行 AI 字幕辨識...")
            srt_path = f"{folder}/subtitles.srt"
            
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel("base", device="cpu", compute_type="int8")
                segments, _ = model.transcribe(mixed_wav, beam_size=5)
                
                with open(srt_path, "w", encoding="utf-8") as f:
                    for i, seg in enumerate(segments, 1):
                        f.write(f"{i}\n{self._format_srt_time(seg.start)} --> {self._format_srt_time(seg.end)}\n{seg.text}\n\n")
            except Exception as e:
                print(f"Whisper failed: {e}")
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write("1\n00:00:00,000 --> 00:00:05,000\n(字幕辨識加載中或失敗)\n")

            # 3. 影片渲染 (動態合成)
            print("[Record] 正在壓製動態彈跳頭像影片...")
            output_mp4 = f"{folder}/output_video.mp4"
            
            # 基本 FFmpeg 指令架構
            # 輸入 0: 黑色背景, 輸入 1: 混合音軌, 接下來是頭像
            inputs = ["-f", "lavfi", "-i", "color=c=black:s=1280x720:r=24", "-i", mixed_wav]
            filter_parts = ["[0:v]"]
            
            # 為每個用戶增加頭像輸入與動態位置
            for i, (uid, path) in enumerate(avatar_paths.items(), 2):
                inputs.extend(["-i", path])
                x_pos = 100 + (i-2)*250
                # 簡單的彈跳效果：循環彈跳 (後續可優化為對齊說話點)
                bounce_expr = f"300-20*gt(sin(t*2.5),0.7)"
                
                prev_label = filter_parts[-1]
                new_label = f"v{i-2}"
                # 縮放並疊加
                filter_parts.append(f"[{i}:v]scale=200:200[av{i}];[{prev_label}][av{i}]overlay=x={x_pos}:y='{bounce_expr}'[{new_label}]")

            # 最後加上字幕燒製
            last_label = filter_parts[-1]
            filter_parts.append(f"[{last_label}]subtitles={srt_path}:force_style='FontSize=24,Alignment=2'[outv]")

            # 執行渲染
            subprocess.run([
                "ffmpeg", "-y"] + inputs + [
                "-filter_complex", ";".join(filter_parts[1:]),
                "-map", "[outv]", "-map", "1:a",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", 
                "-shortest", output_mp4
            ], check=True, capture_output=True)

            return output_mp4

        except Exception as e:
            print(f"Render Task Error: {e}")
            return None

    def _format_srt_time(self, seconds):
        td = time.gmtime(seconds)
        ms = int((seconds % 1) * 1000)
        return f"{time.strftime('%H:%M:%S', td)},{ms:03d}"

async def setup(bot):
    await bot.add_cog(RecordCog(bot))
