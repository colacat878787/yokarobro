import discord
from discord.ext import commands
import shutil
import subprocess
import asyncio
import os
import sys
import platform

class SystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tools = {
            "yt-dlp": "音樂解析核心",
            "spotify-dlp": "Spotify 專業解析引擎",
            "ffmpeg": "音訊處理引擎"
        }
        # 啟動時自動檢查並修復
        asyncio.create_task(self.auto_heal())

    async def auto_heal(self):
        """啟動時自動掃描與安裝缺失套件"""
        print("🔍 [System] 啟動自動診斷程序...")
        
        # 檢查 spotify-dlp
        if not shutil.which("spotify-dlp"):
            print("⚠️ [System] 偵測到缺少 spotify-dlp，正在嘗試自動安裝...")
            try:
                # 執行 pip install
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pip", "install", "spotify-dlp",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                print("✅ [System] spotify-dlp 自動安裝嘗試完成。")
            except Exception as e:
                print(f"❌ [System] 自動安裝失敗: {e}")
        else:
            print("✅ [System] spotify-dlp 已就緒。")

    @commands.group(name='sys', aliases=['系統'], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def sys_group(self, ctx):
        """系統管理指令群"""
        await ctx.send("❓ 請輸入子指令：`check` (診斷), `repair` (修復), `info` (狀態)")

    @sys_group.command(name='check', aliases=['診斷'])
    async def check(self, ctx):
        """專業診斷目前系統依賴項狀態"""
        embed = discord.Embed(title="🩺 Yokaro 系統診斷報告", color=0x3498db)
        embed.timestamp = discord.utils.utcnow()

        status_text = ""
        for tool, desc in self.tools.items():
            path = shutil.which(tool)
            if path:
                status_text += f"✅ **{tool}**: 已就緒\n> *{desc}*\n> 📍 `{path}`\n\n"
            else:
                status_text += f"❌ **{tool}**: 找不到組件\n> *{desc}*\n> ⚠️ 請嘗試使用 `!sys repair` 修復\n\n"

        embed.add_field(name="📦 依賴項狀態", value=status_text, inline=False)

        # 系統資訊
        sys_info = (
            f"💻 **OS**: {platform.system()} {platform.release()}\n"
            f"🐍 **Python**: {platform.python_version()}\n"
            f"🏮 **Latency**: {round(self.bot.latency * 1000)}ms"
        )
        embed.add_field(name="🖥️ 環境控制台", value=sys_info, inline=False)
        embed.set_footer(text=f"診斷者: {self.bot.user.name} | 管理員權限已驗證")
        
        await ctx.send(embed=embed)

    @sys_group.command(name='repair', aliases=['修復'])
    async def repair(self, ctx):
        """手動觸發自癒程序，嘗試補齊缺失套件"""
        msg = await ctx.send("🛠️ **正在啟動修復程序...** 請耐心等候洛洛搬運零件。")
        
        results = []
        # 強制執行一次 pip install spotify-dlp
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", "--upgrade", "spotify-dlp",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                results.append("✅ `spotify-dlp` 已成功安裝或更新。")
            else:
                results.append(f"❌ `spotify-dlp` 安裝失敗: {stderr.decode()[:100]}")
        except Exception as e:
            results.append(f"❌ 修復過程發生異常: {e}")

        final_msg = "\n".join(results)
        await msg.edit(content=f"⚙️ **修復完成！結果報表：**\n{final_msg}")

    @sys_group.command(name='info', aliases=['狀態'])
    async def info(self, ctx):
        """快速查看目前系統資源佔用 (需要 psutil)"""
        try:
            import psutil
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            await ctx.send(f"📊 **系統負載**：\n> CPU: {cpu}%\n> RAM: {ram}%")
        except ImportError:
            await ctx.send("⚠️ 缺少 `psutil` 模組，無法顯示精確負載。")

async def setup(bot):
    await bot.add_cog(SystemCog(bot))
