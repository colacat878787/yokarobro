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

    @tasks.loop(minutes=3) # 每 3 分鐘自動檢查一次 Git 更新
    async def check_update(self):
        try:
            # 1. 抓取遠部遠端最新狀態 (這不會變動本地檔案)
            await asyncio.to_thread(subprocess.run, ["git", "fetch"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 2. 比較本地 HEAD 與遠端 origin/main 的 Commit Hash 是否不同
            local_hash = await asyncio.to_thread(subprocess.check_output, ["git", "rev-parse", "HEAD"])
            remote_hash = await asyncio.to_thread(subprocess.check_output, ["git", "rev-parse", "origin/main"])
            
            if local_hash.strip() != remote_hash.strip():
                print("🔄 [自動更新] 偵測到遠端 GitHub 有新版本！正在自動拉取更新...")
                
                # 3. 執行 git pull 更新程式碼
                await asyncio.to_thread(subprocess.run, ["git", "pull", "origin", "main"], check=True)
                
                print("✅ [自動更新] 更新完成，準備重新啟動機器人拉取新系統...")
                
                # 4. 強制結束程序，Pterodactyl 面板會秒速自動將機器人重啟，完美銜接新代碼
                os._exit(0)
        except Exception as e:
            # 原諒我偷偷忽略錯誤，可能是沒有 git 目錄或沒設好 origin
            pass

    @check_update.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(AutoUpdaterCog(bot))
