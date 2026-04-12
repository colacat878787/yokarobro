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

    @tasks.loop(seconds=3)
    async def check_update(self):
        try:
            env = dict(os.environ, GIT_TERMINAL_PROMPT="0")

            # 靜默取得遠端最新 commit hash
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "ls-remote", "origin", "main"],
                capture_output=True, text=True, timeout=10, env=env
            )
            if result.returncode != 0:
                # 只有錯誤才 log
                print(f"⚠️ [自動更新] 無法連接 GitHub：{result.stderr.strip()}")
                return

            parts = result.stdout.strip().split()
            if not parts:
                return

            remote_hash = parts[0]
            local_hash = (await asyncio.to_thread(
                subprocess.check_output,
                ["git", "rev-parse", "HEAD"],
                text=True
            )).strip()

            # 相同就完全靜默，不印任何東西
            if local_hash == remote_hash:
                return

            # ── 有新版本才開始 log ──
            print("====================================")
            print(f"🔄 [自動更新] 發現新版本！")
            print(f"   本地: {local_hash[:7]}  →  遠端: {remote_hash[:7]}")
            print("⏬ [自動更新] 正在強制同步...")

            await asyncio.to_thread(
                subprocess.run,
                ["git", "fetch", "--all"], check=True, timeout=15, env=env, capture_output=True
            )
            reset = await asyncio.to_thread(
                subprocess.run,
                ["git", "reset", "--hard", "origin/main"],
                check=True, capture_output=True, text=True, timeout=15, env=env
            )

            print(f"✅ [自動更新] 同步完成：{reset.stdout.strip()}")
            print("🔁 [自動更新] 重啟機器人...")
            print("====================================")
            os._exit(0)

        except subprocess.TimeoutExpired:
            print("⚠️ [自動更新] 連接 GitHub 超時，跳過本次檢查。")
        except subprocess.CalledProcessError as e:
            print(f"❌ [自動更新] Git 指令失敗：{e}")
        except Exception as e:
            print(f"❌ [自動更新] 例外錯誤：{e}")

    @check_update.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
        print("👁️  [自動更新] 已啟動，每 3 秒靜默監控 GitHub...")

    @commands.command(name='update', aliases=['系統更新', '強制更新'])
    @commands.has_permissions(administrator=True)
    async def manual_update(self, ctx):
        """手動觸發強制更新"""
        msg = await ctx.send("🏃 洛洛正在向 GitHub 小跑步...")
        try:
            env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
            await asyncio.to_thread(subprocess.run, ["git", "fetch", "--all"], check=True, timeout=15, env=env, capture_output=True)

            local = (await asyncio.to_thread(subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True)).strip()
            remote = (await asyncio.to_thread(subprocess.check_output, ["git", "rev-parse", "origin/main"], text=True)).strip()

            if local == remote:
                await msg.edit(content="✅ 目前已是最新版本，不需要更新。")
                return

            await msg.edit(content=f"🔄 發現新版本！正在強制同步 (`{local[:7]}` → `{remote[:7]}`)...")
            await asyncio.to_thread(
                subprocess.run,
                ["git", "reset", "--hard", "origin/main"],
                check=True, timeout=15, env=env, capture_output=True
            )
            await msg.edit(content="✅ 同步完成！洛洛正在重啟，請稍候...")
            print("[強制更新] 管理員手動觸發更新，準備重啟。")
            os._exit(0)

        except subprocess.TimeoutExpired:
            await msg.edit(content="❌ 連接 GitHub 超時！")
        except Exception as e:
            await msg.edit(content=f"❌ 更新失敗：{e}")

async def setup(bot):
    await bot.add_cog(AutoUpdaterCog(bot))
