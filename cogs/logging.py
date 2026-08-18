"""
cogs/logging.py
機器人 Log 系統 - 記錄一舉一動
記錄：加入/退出伺服器、指令執行、AI 對話、錯誤等。
設定 Log 頻道：!logchannel 或透過 !panel 的按鈕。
"""
import discord
from discord.ext import commands
import json
import os
from datetime import datetime

LOG_CHANNEL_FILE = "bot_log_channel.json"


def load_log_channel_id():
    if os.path.exists(LOG_CHANNEL_FILE):
        try:
            with open(LOG_CHANNEL_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("channel_id", 0) or 0)
        except:
            pass
    return None


def save_log_channel_id(channel_id):
    with open(LOG_CHANNEL_FILE, "w", encoding="utf-8") as f:
        json.dump({"channel_id": int(channel_id)}, f)


class LoggingCog(commands.Cog):
    """機器人 Log 系統 - 記錄所有事件"""

    def __init__(self, bot):
        self.bot = bot

    def _get_channel(self):
        cid = load_log_channel_id()
        if not cid:
            return None
        return self.bot.get_channel(cid)

    async def log(self, title, description=None, color=0x5865F2, fields=None, thumbnail=None):
        """傳送 log embed 到設定頻道，同時寫到 console"""
        try:
            channel = self._get_channel()
            embed = discord.Embed(title=title, description=description, color=color,
                                  timestamp=datetime.now())
            if fields:
                for name, value in fields.items():
                    embed.add_field(name=name, value=value, inline=False)
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)
            embed.set_footer(text="優卡洛 Log 系統")
            print(f"📋 [LOG] {title}: {description}")
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            print(f"[LOG] 無法發送 log: {e}")

    @commands.command(name="logchannel", aliases=["log頻道"])
    @commands.is_owner()
    async def logchannel(self, ctx):
        """設定當前頻道為機器人 Log 頻道"""
        save_log_channel_id(ctx.channel.id)
        await ctx.send(f"✅ 已將 {ctx.channel.mention} 設定為機器人 Log 頻道！所有記錄將發送到這裡。")

    # ── 事件監聽 ──────────────────────────

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """機器人加入伺服器"""
        try:
            await self.log(
                "🟢 機器人加入伺服器",
                None,
                color=0x2ecc71,
                fields={
                    "🏷️ 伺服器": f"**{guild.name}** (`{guild.id}`)",
                    "👥 成員數": f"{guild.member_count} 人",
                    "👑 擁有者": f"{guild.owner} ({guild.owner_id})" if guild.owner_id else "未知",
                },
                thumbnail=guild.icon.url if guild.icon else None,
            )
        except Exception as e:
            print(f"[LOG] guild_join 記錄失敗: {e}")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """機器人退出伺服器"""
        try:
            await self.log(
                "🔴 機器人退出伺服器",
                None,
                color=0xe74c3c,
                fields={
                    "🏷️ 伺服器": f"**{guild.name}** (`{guild.id}`)",
                    "👥 成員數": f"{guild.member_count} 人",
                },
            )
        except Exception as e:
            print(f"[LOG] guild_remove 記錄失敗: {e}")

    @commands.Cog.listener()
    async def on_command(self, ctx):
        """有使用者執行了指令"""
        try:
            await self.log(
                "⚡ 指令執行",
                None,
                color=0x5865F2,
                fields={
                    "👤 使用者": f"{ctx.author} (`{ctx.author.id}`)",
                    "📍 位置": f"{ctx.guild.name} / #{ctx.channel.name}" if ctx.guild else "DM",
                    "⌨️ 指令": f"`!{ctx.invoked_with}`",
                },
            )
        except Exception as e:
            print(f"[LOG] command 記錄失敗: {e}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        """指令執行成功"""
        try:
            await self.log(
                "✅ 指令成功",
                f"`!{ctx.invoked_with}` 執行成功",
                color=0x2ecc71,
            )
        except Exception as e:
            print(f"[LOG] command_completion 記錄失敗: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """指令出錯"""
        try:
            await self.log(
                "❌ 指令錯誤",
                None,
                color=0xe74c3c,
                fields={
                    "👤 使用者": f"{ctx.author} (`{ctx.author.id}`)",
                    "⌨️ 指令": f"`!{ctx.invoked_with}`",
                    "⚠️ 錯誤": f"```{str(error)[:500]}```",
                },
            )
        except Exception as e:
            print(f"[LOG] command_error 記錄失敗: {e}")

    async def log_ai(self, user, user_input, reply, guild_name, channel_name):
        """記錄 AI 互動 (由 ai.py 呼叫)"""
        try:
            await self.log(
                "🤖 AI 對話",
                None,
                color=0x9b59b6,
                fields={
                    "👤 使用者": f"{user} (`{user.id}`)",
                    "📍 位置": f"{guild_name} / #{channel_name}" if guild_name else "DM",
                    "💬 用戶說": f"```{user_input[:800]}```",
                    "✨ 小幽回": f"```{reply[:800]}```",
                },
            )
        except Exception as e:
            print(f"[LOG] ai 記錄失敗: {e}")


async def setup(bot):
    await bot.add_cog(LoggingCog(bot))