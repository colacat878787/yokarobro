import discord
from discord.ext import commands, tasks
import subprocess
import os
import asyncio
import json

CHANGELOG_FILE = "changelog_channel.json"

class AutoUpdaterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.changelog_channel_id = self._load_channel()
        self.check_update.start()

    def cog_unload(self):
        self.check_update.cancel()

    def _load_channel(self):
        if os.path.exists(CHANGELOG_FILE):
            try:
                with open(CHANGELOG_FILE, "r") as f:
                    return json.load(f).get("channel_id")
            except: pass
        return None

    def _save_channel(self, channel_id):
        with open(CHANGELOG_FILE, "w") as f:
            json.dump({"channel_id": channel_id}, f)

    def _get_git_log(self, from_hash, to_hash="HEAD"):
        """取得兩個 commit 之間的更新紀錄"""
        try:
            log = subprocess.check_output(
                ["git", "log", f"{from_hash}..{to_hash}", "--oneline", "--no-merges"],
                text=True
            ).strip()
            return log if log else "（無新增 commit 紀錄）"
        except:
            return "（無法取得 commit 紀錄）"

    async def _notify_changelog(self, old_hash, new_hash):
        """在更新頻道發布更新通知"""
        if not self.changelog_channel_id:
            return
        channel = self.bot.get_channel(self.changelog_channel_id)
        if not channel:
            return
        try:
            log = self._get_git_log(old_hash, new_hash)
            embed = discord.Embed(
                title="🔄 優卡洛 自動更新完成！",
                description="洛洛剛剛更新完了喔！以下是本次的更新內容：",
                color=0x2ecc71
            )
            embed.add_field(name="📦 版本變化", value=f"`{old_hash[:7]}` → `{new_hash[:7]}`", inline=False)
            embed.add_field(
                name="📝 更新內容",
                value=f"```\n{log[:1000]}\n```" if log else "無詳細紀錄",
                inline=False
            )
            embed.set_footer(text="洛洛更新完畢後已自動重啟！嗷嗷嗷～")
            await channel.send(embed=embed)
        except Exception as e:
            print(f"⚠️ [更新通知] 無法發送更新訊息: {e}")

    @tasks.loop(minutes=30)
    async def check_update(self):
        try:
            env = dict(os.environ, GIT_TERMINAL_PROMPT="0")

            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "ls-remote", "origin", "main"],
                capture_output=True, text=True, timeout=10, env=env
            )
            if result.returncode != 0:
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

            # 相同就完全靜默
            if local_hash == remote_hash:
                return

            # ── 發現新版本 ──
            print("====================================")
            print(f"🔄 [自動更新] 發現新版本！")
            print(f"   本地: {local_hash[:7]}  →  遠端: {remote_hash[:7]}")
            print("⏬ [自動更新] 正在強制同步...")

            await asyncio.to_thread(
                subprocess.run,
                ["git", "fetch", "--all"], check=True, timeout=15, env=env, capture_output=True
            )
            await asyncio.to_thread(
                subprocess.run,
                ["git", "reset", "--hard", "origin/main"],
                check=True, capture_output=True, text=True, timeout=15, env=env
            )

            print(f"✅ [自動更新] 同步完成，馬上重啟！")
            print("====================================")

            # 在重啟前發送更新通知到頻道
            await self._notify_changelog(local_hash, remote_hash)

            # 立即重啟，不等待
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

    # ─────────────────────────────────────
    #  指令區
    # ─────────────────────────────────────

    @commands.command(name='set_changelog', aliases=['更新頻道', '設定更新頻道'])
    @commands.has_permissions(administrator=True)
    async def set_changelog(self, ctx):
        """將當前頻道設定為自動更新通知頻道"""
        self.changelog_channel_id = ctx.channel.id
        self._save_channel(ctx.channel.id)
        await ctx.send(f"✅ 已將 **#{ctx.channel.name}** 設為更新通知頻道！\n以後洛洛每次自動更新，都會在這裡發布更新內容喔。嗷嗷嗷～")

    @commands.command(name='changelog', aliases=['更新紀錄', '版本紀錄'])
    async def changelog(self, ctx, count: int = 5):
        """查看最近的更新紀錄"""
        try:
            log = subprocess.check_output(
                ["git", "log", f"-{min(count, 15)}", "--pretty=format:%h %s (%ar)"],
                text=True
            ).strip()
            if not log:
                await ctx.send("嗷～找不到任何更新紀錄耶。")
                return
            embed = discord.Embed(
                title=f"📜 洛洛最近 {min(count, 15)} 筆更新紀錄",
                description=f"```\n{log}\n```",
                color=0x3498db
            )
            embed.set_footer(text="使用 !更新紀錄 [數量] 可以查看更多紀錄")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ 無法讀取更新紀錄：{e}")

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
            await msg.edit(content="✅ 同步完成！洛洛馬上重啟...")
            await self._notify_changelog(local, remote)
            os._exit(0)

        except subprocess.TimeoutExpired:
            await msg.edit(content="❌ 連接 GitHub 超時！")
        except Exception as e:
            await msg.edit(content=f"❌ 更新失敗：{e}")

async def setup(bot):
    await bot.add_cog(AutoUpdaterCog(bot))
