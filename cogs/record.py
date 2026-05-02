import discord
from discord.ext import commands
print("🚀 [DEBUG] record.py 文件正在被 Python 讀取中...")
import asyncio
import os
import time
import subprocess
import json
import shutil
import logging
from concurrent.futures import ThreadPoolExecutor

# 靜音插件的報錯日誌，避免大量損壞包報錯淹沒系統
logging.getLogger('discord.ext.voice_recv').setLevel(logging.CRITICAL)

# 注意：我們需要 discord-ext-voice-recv 插件
try:
    import discord.ext.voice_recv as voice_recv
    HAS_VOICE_RECV = True
    print("💠 [錄影機] 語音接收模組載入成功！")
except ImportError as e:
    HAS_VOICE_RECV = False
    print(f"⚠️ [錄影機] 語音接收模組載入失敗: {e}")
except Exception as e:
    HAS_VOICE_RECV = False
    print(f"❌ [錄影機] 載入過程發生非預期錯誤: {e}")

class AudioBuffer:
    def __init__(self, user, folder):
        self.user = user
        self.folder = folder
        self.file_path = f"{folder}/user_{user.id}.pcm"
        try:
            self.file = open(self.file_path, "wb")
        except Exception as e:
            print(f"⚠️ [Buffer] 無法開啟檔案: {e}")
            self.file = None
        self.start_time = time.time()

    def write(self, data):
        if self.file:
            self.file.write(data)

    def close(self):
        if self.file:
            self.file.close()

class SyncedAudioSink(voice_recv.AudioSink):
    def __init__(self, folder, guild_id):
        super().__init__()
        self.folder = folder
        self.guild_id = guild_id
        self.buffers = {}
        self.start_time = time.time()

    def wants_opus(self) -> bool:
        return False # 請求 PCM 資料

    def write(self, user, data):
        try:
            if not data or not data.pcm: return
            
            # 1. 存檔錄音
            if user not in self.buffers:
                self.buffers[user] = AudioBuffer(user, self.folder)
            self.buffers[user].write(data.pcm)
            
            # 2. 秘密電線：傳給網頁儀表板
            try:
                from cogs.music_web import audio_queues
                if self.guild_id not in audio_queues:
                    audio_queues[self.guild_id] = []
                # 限制緩衝區大小，避免內存爆炸 (只保留最後 1 秒的數據)
                if len(audio_queues[self.guild_id]) > 50: 
                    audio_queues[self.guild_id].pop(0)
                audio_queues[self.guild_id].append(data.pcm)
            except:
                pass
        except Exception:
            pass # 靜默處理損壞包

    def cleanup(self):
        for buffer in self.buffers.values():
            try:
                buffer.close()
            except:
                pass

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

        # 這裡加一個穩定化小延遲
        await asyncio.sleep(1)

        # 建立錄音資料匣
        rec_id = int(time.time())
        folder = f"temp/rec_{rec_id}"
        os.makedirs(folder, exist_ok=True)

        sink = SyncedAudioSink(folder, ctx.guild.id)
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

        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(self.executor, self._process_render_sync, sink)
        asyncio.create_task(self._wait_and_send(ctx, future, msg))

    async def _wait_and_send(self, ctx, future, status_msg):
        try:
            video_path = await future
            if video_path and os.path.exists(video_path):
                await status_msg.edit(content="🎉 剪輯完成！正在傳送影片... 嗷嗚！")
                await ctx.send(file=discord.File(video_path))
                shutil.rmtree(os.path.dirname(video_path), ignore_errors=True)
            else:
                await status_msg.edit(content="❌ 哎呀，影片合成時發生意外了！請培檢查後台 Log 幫助洛洛除錯。")
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
                    if res.status_code == 200:
                        with open(p, "wb") as f: f.write(res.content)
                        avatar_paths[user.id] = p
                except Exception as e:
                    print(f"⚠️ [Record] 下載頭像失敗 ({user.id}): {e}")

            mixed_wav = f"{folder}/mixed.wav"
            
            # 建立多音軌混音
            amix_inputs = []
            valid_buffers = []
            for buf in sink.buffers.values():
                if os.path.exists(buf.file_path) and os.path.getsize(buf.file_path) > 0:
                    amix_inputs.extend(["-f", "s16le", "-ar", "48000", "-ac", "2", "-i", buf.file_path])
                    valid_buffers.append(buf)
            
            if not amix_inputs:
                print("❌ [Record] 沒有錄到任何音效數據！")
                return None

            print(f"[Record] 正在混音 {len(valid_buffers)} 位說話者的音軌...")
            subprocess.run([
                "ffmpeg", "-y"] + amix_inputs + [
                "-filter_complex", f"amix=inputs={len(valid_buffers)}:duration=longest",
                mixed_wav
            ], check=True, capture_output=True)

            # 2. AI 辨識 (Faster-Whisper) - 非強制
            print("[Record] 正在嘗試執行 AI 字幕辨識...")
            srt_path = f"{folder}/subtitles.srt"
            use_subtitles = False
            
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel("base", device="cpu", compute_type="int8")
                segments, _ = model.transcribe(mixed_wav, beam_size=5)
                
                with open(srt_path, "w", encoding="utf-8") as f:
                    for i, seg in enumerate(segments, 1):
                        f.write(f"{i}\n{self._format_srt_time(seg.start)} --> {self._format_srt_time(seg.end)}\n{seg.text}\n\n")
                use_subtitles = True
                print("✅ [Record] 字幕辨識成功！")
            except Exception as e:
                print(f"⚠️ [Record] 跳過字幕辨識 (原因: {e})")

            # 3. 影片渲染
            print("[Record] 最終壓製動態影片...")
            output_mp4 = f"{folder}/output_video.mp4"
            
            inputs = ["-f", "lavfi", "-i", "color=c=black:s=1280x720:r=24", "-i", mixed_wav]
            filter_complex = ""
            current_v = "0:v"
            
            input_ptr = 2
            for uid, path in avatar_paths.items():
                if not os.path.exists(path): continue
                inputs.extend(["-i", path])
                x_pos = 100 + (input_ptr-2)*300
                bounce_expr = f"300-20*gt(sin(t*2.5),0.7)"
                
                filter_complex += f"[{input_ptr}:v]scale=200:200[av{uid}];"
                next_v = f"v{input_ptr}"
                filter_complex += f"[{current_v}][av{uid}]overlay=x={x_pos}:y='{bounce_expr}'[{next_v}];"
                current_v = next_v
                input_ptr += 1

            if use_subtitles and os.path.exists(srt_path):
                safe_srt = srt_path.replace("\\", "/").replace(":", "\\:")
                filter_complex += f"[{current_v}]subtitles='{safe_srt}':force_style='FontSize=24,Alignment=2'[outv]"
            else:
                filter_complex += f"[{current_v}]null[outv]"

            res = subprocess.run([
                "ffmpeg", "-y"] + inputs + [
                "-filter_complex", filter_complex,
                "-map", "[outv]", "-map", "1:a",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", 
                "-shortest", output_mp4
            ], capture_output=True, text=True)

            if res.returncode != 0:
                print(f"❌ [FFmpeg Error]\n{res.stderr}")
                return None

            return output_mp4

        except Exception as e:
            print(f"❌ [Record] 渲染崩潰: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _format_srt_time(self, seconds):
        td = time.gmtime(seconds)
        ms = int((seconds % 1) * 1000)
        return f"{time.strftime('%H:%M:%S', td)},{ms:03d}"

async def setup(bot):
    await bot.add_cog(RecordCog(bot))
