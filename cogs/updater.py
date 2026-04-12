import discord
from discord.ext import commands, tasks
import subprocess
import os
import asyncio

class AutoUpdaterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_update.start()

    def cog_unload(self):
        self.check_update.cancel()

    @tasks.loop(seconds=3) # 每 3 秒自動檢查一次 Git 更新
    async def check_update(self):
        try:
            env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
            
            # 使用 ls-remote 輕量化取得遠端最新的 commit hash (不佔用磁碟存取)
            process = await asyncio.to_thread(subprocess.run, ["git", "ls-remote", "origin", "main"], capture_output=True, text=True, timeout=10, env=env)
            if process.returncode != 0:
                print(f"⚠️ [自動更新] 無法獲取遠端狀態，Git 錯誤:\n{process.stderr}")
                return
                
            out_lines = process.stdout.strip().split()
            if not out_lines:
                return
            remote_hash = out_lines[0]
            
            local_hash = await asyncio.to_thread(subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True)
            local_hash = local_hash.strip()
            
            if local_hash != remote_hash:
                print("====================================")
                print(f"🔄 [自動更新] 發現遠端 GitHub 有新版本！")
                print(f"📌 本地版本: {local_hash[:7]}")
                print(f"⭐ 遠端版本: {remote_hash[:7]}")
                print("⏬ [自動更新] 正在執行 git fetch 與 git pull...")
                
                # 正式執行拉取
                print("⏬ [自動更新] 正在執行 git fetch 與 git reset --hard...")
                await asyncio.to_thread(subprocess.run, ["git", "fetch", "--all"], check=True, timeout=15, env=env)
                
                # 強制重打，抹除本地可能產生的衝突 (例如自動生成的 json 被 git 誤認或是權限問題)
                reset_res = await asyncio.to_thread(subprocess.run, ["git", "reset", "--hard", "origin/main"], check=True, capture_output=True, text=True, timeout=15, env=env)
                
                print(f"📥 [自動更新] 強制同步成功！日誌：\n{reset_res.stdout}")
                print("✅ [自動更新] 代碼已完全同步至最新版本，準備重啟...")
                print("====================================")
                os._exit(0)
        except Exception as e:
            print(f"❌ [自動更新] 發生例外錯誤: {e}")

    @check_update.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
        print("🚀 [自動更新] 模組準備就緒！已開始每 3 秒進行極速心跳檢查！")

    @commands.command(name='update', aliases=['系統更新', '強制更新'])
    @commands.has_permissions(administrator=True)
    async def manual_update(self, ctx):
        """手動觸發拉取 GitHub 更新"""
        msg = await ctx.send("🏃 洛洛正在向 GitHub 小跑步請求最新代碼...")
        try:
            env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
            await asyncio.to_thread(subprocess.run, ["git", "fetch"], check=True, timeout=15, env=env, capture_output=True)
            local_hash = await asyncio.to_thread(subprocess.check_output, ["git", "rev-parse", "HEAD"], timeout=5)
            remote_hash = await asyncio.to_thread(subprocess.check_output, ["git", "rev-parse", "origin/main"], timeout=5)
            
            if local_hash.strip() != remote_hash.strip():
                await msg.edit(content="🔄 哇塞！發現熱騰騰的新代碼！正在強制同步安裝，洛洛馬上重啟！嗷嗷嗷～")
                await asyncio.to_thread(subprocess.run, ["git", "fetch", "--all"], check=True, timeout=15, env=env)
                await asyncio.to_thread(subprocess.run, ["git", "reset", "--hard", "origin/main"], check=True, timeout=15, env=env)
                os._exit(0)
            else:
                await msg.edit(content="✅ 目前洛洛已經是最新的程式碼囉！不需要更新。")
        except subprocess.TimeoutExpired:
            await msg.edit(content="❌ 嗷...連線 GitHub 超時！面板可能把外網封鎖了，或者 Git 卡住了。")
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode('utf-8', errors='ignore') if getattr(e, 'stderr', None) else str(e)
            await msg.edit(content=f"❌ 嗷...從 GitHub 抓取代碼失敗惹：\n```\n{err_msg[:500]}\n```")
        except Exception as e:
            await msg.edit(content=f"❌ 發生未知錯誤：{e}")

async def setup(bot):
    await bot.add_cog(AutoUpdaterCog(bot))
