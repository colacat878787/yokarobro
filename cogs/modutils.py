"""
cogs/modutils.py
頻道管理工具
指令：
  !clear <數量> [@成員 / bots]  - 大量刪除訊息（管理員）
     範例: !clear 50
           !clear 100 bots          - 只刪機器人訊息
           !clear 30 @小美          - 只刪指定成員的訊息
  !slowmode <秒數|off>          - 設定頻道慢速模式（管理員）
     範例: !slowmode 10s / !slowmode 5 / !slowmode off
"""

import asyncio
import discord
from discord.ext import commands

from utils.data_store import parse_duration, format_duration


class ModUtilsCog(commands.Cog):
    """🧹 頻道管理工具 - 清訊與慢速模式"""

    def __init__(self, bot):
        self.bot = bot

    # ===== 大量刪除訊息 =====
    @commands.command(name="clear", aliases=["清訊", "purge"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 10, *, target: str = None):
        """大量刪除訊息：!clear <數量> [@成員或 bots]"""
        amount = max(1, min(amount, 1000))

        member = None
        only_bots = False
        if target:
            target = target.strip()
            if target.lower() in ("bots", "bot", "機器人", "bot訊息"):
                only_bots = True
            else:
                try:
                    converter = commands.MemberConverter()
                    member = await converter.convert(ctx, target)
                except commands.CommandError:
                    await ctx.send("❌ 無法辨識目標。可以使用 `@成員` 或 `bots`。")
                    return

        # 構建過濾條件
        def _check(m: discord.Message) -> bool:
            if only_bots:
                return m.author.bot
            if member is not None:
                return m.author.id == member.id
            return True

        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        # Discord 一次 bulk 上限 100，迴圈分批
        total_deleted = 0
        remaining = amount
        err = None
        while remaining > 0:
            batch = min(remaining, 100)
            try:
                deleted = await ctx.channel.purge(
                    limit=batch,
                    check=_check,
                    bulk=True,
                )
            except discord.Forbidden as e:
                err = e
                break
            remaining -= batch
            total_deleted += len(deleted)
            if len(deleted) < batch:
                break  # 頻道沒有更多訊息了

        if total_deleted == 0:
            msg = "⚠️ 沒有刪除到任何訊息"
            if err:
                msg = f"❌ 刪除失敗：{err}"
            notice = await ctx.send(msg)
            await asyncio.sleep(5)
            try:
                await notice.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            return

        suffix = ""
        if only_bots:
            suffix = "（bot 訊息）"
        elif member is not None:
            suffix = f"（{member.display_name} 的訊息）"
        notice = await ctx.send(f"🧹 已刪除 **{total_deleted}** 則訊息{suffix}！")
        await asyncio.sleep(5)
        try:
            await notice.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    # ===== 慢速模式 =====
    @commands.command(name="slowmode", aliases=["慢速", "慢速模式"])
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(self, ctx, value: str = None):
        """設定頻道慢速模式：!slowmode <秒數|off>（最長 6 小時）"""
        if value is None:
            current = ctx.channel.slowmode_delay
            if current:
                await ctx.send(f"⏳ 當前慢速模式：**每 {current} 秒** 一則訊息\n使用 `!slowmode off` 關閉")
            else:
                await ctx.send("⏳ 這個頻道目前沒有慢速模式。\n使用 `!slowmode <秒數>` 開啟。")
            return

        value = value.strip().lower()
        if value in ("off", "關閉", "cancel", "0"):
            delay = 0
        else:
            delay = parse_duration(value)
            if delay == 0 and value.isdigit():
                delay = int(value)
            if delay <= 0:
                await ctx.send("❌ 無法解析時間。範例：`!slowmode 10s`、`!slowmode 5m`、`!slowmode off`")
                return
            if delay > 21600:
                await ctx.send("❌ 慢速模式最長為 6 小時（21600 秒）。")
                return

        await ctx.channel.edit(slowmode_delay=delay, reason=f"{ctx.author} 使用 !slowmode")
        if delay == 0:
            await ctx.send("✅ 已關閉慢速模式！")
        else:
            await ctx.send(f"✅ 已設定慢速模式：**每 {format_duration(delay)}** 一則訊息")


async def setup(bot):
    await bot.add_cog(ModUtilsCog(bot))
