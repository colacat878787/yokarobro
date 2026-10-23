"""
cogs/sticky.py
置頂常駐訊息（Sticky Message）
在頻道設定一則常駐訊息，每當有人發言，機器人就會把舊的常駐訊息刪除，
再把常駐訊息重新貼到最新位置。

指令：
  !sticky <內容>     - 在當前頻道設定常駐訊息（會自動刪除指令本身）
  !sticky off        - 關閉當前頻道的常駐訊息
  !sticky list       - 列出本伺服器所有常駐訊息
資料存 data/sticky.json。
"""

import asyncio

import discord
from discord.ext import commands

from utils.data_store import DataStore


class StickyCog(commands.Cog):
    """📌 置頂常駐訊息"""

    def __init__(self, bot):
        self.bot = bot
        # {channel_id: {"content": str, "guild_id": int}}
        self.store = DataStore("sticky.json")
        self._locks = {}  # channel_id -> bool 防止重複貼

    def cog_unload(self):
        pass

    # ===== 設定常駐訊息 =====
    @commands.group(name="sticky", aliases=["置頂訊息", "常駐訊息"], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def sticky(self, ctx, *, content: str = None):
        """設定常駐訊息：!sticky <內容>"""
        if content is None:
            current = self.store.get(ctx.channel.id)
            if current:
                await ctx.send(
                    f"📌 本頻道已設定常駐訊息：\n> {current['content'][:150]}\n"
                    "使用 `!sticky off` 關閉。"
                )
            else:
                await ctx.send("📌 **常駐訊息用法**\n`!sticky <內容>` — 把訊息常駐在頻道最下方\n`!sticky off` — 取消")
            return

        # 刪除使用者的指令訊息，保持頻道乾淨
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        self.store.set(str(ctx.channel.id), {"content": content, "guild_id": ctx.guild.id})
        # 立即貼一次
        await self._post_sticky(ctx.channel)
        confirms = await ctx.send("✅ 已設定常駐訊息！")
        await asyncio.sleep(3)
        try:
            await confirms.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    @sticky.command(name="off", aliases=["取消"])
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def sticky_off(self, ctx):
        """關閉本頻道的常駐訊息"""
        current = self.store.get(ctx.channel.id)
        if not current:
            await ctx.send("❌ 本頻道沒有設定常駐訊息。")
            return
        self.store.delete(str(ctx.channel.id))
        # 刪掉舊的常駐訊息本體
        msg_id = current.get("msg_id")
        if msg_id:
            try:
                old = await ctx.channel.fetch_message(int(msg_id))
                if old.author == self.bot.user:
                    await old.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
        await ctx.send("✅ 已關閉本頻道的常駐訊息。")

    @sticky.command(name="list", aliases=["清單"])
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def sticky_list(self, ctx):
        """列出本伺服器的常駐訊息"""
        lines = []
        for cid, data in self.store.data.items():
            if int(data.get("guild_id", 0)) != ctx.guild.id:
                continue
            ch = self.bot.get_channel(int(cid))
            ch_name = ch.mention if ch else f"（已刪除頻道 {cid}）"
            lines.append(f"• {ch_name}：{data['content'][:60]}")
        if not lines:
            await ctx.send("📋 本伺服器沒有任何常駐訊息。")
            return
        embed = discord.Embed(title="📌 常駐訊息清單", description="\n".join(lines), color=0x3498DB)
        await ctx.send(embed=embed)

    # ===== 常駐貼出 =====
    async def _post_sticky(self, channel: discord.TextChannel):
        if self._locks.get(channel.id):
            return  # 有一個還在處理就緒不重複貼
        self._locks[channel.id] = True
        try:
            current = self.store.get(str(channel.id))
            if not current:
                return
            # 刪除舊的
            old_id = current.get("msg_id")
            if old_id:
                try:
                    old = await channel.fetch_message(int(old_id))
                    if old.author == self.bot.user:
                        await old.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                # 舊的如果是本機器人訊息直接刪
            try:
                sent = await channel.send(
                    f"📌 **常駐訊息**\n{current['content']}\n\n*（管理員可用 `!sticky off` 取消）*"
                )
            except (discord.Forbidden, discord.NotFound):
                return
            current["msg_id"] = sent.id
            self.store.set(str(channel.id), dict(current))
        finally:
            self._locks[channel.id] = False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        current = self.store.get(str(message.channel.id))
        if not current:
            return
        # 設定指令本身（!sticky ...）也要跳過
        if message.content.startswith(("!sticky", "!置頂訊息", "!常駐訊息")):
            # 但要等到設定完確認貼出後，off/list 不會重貼
            return
        # 只在有人「真的」說話後重貼，不要對指令回應也重貼? 這裡僅對成員訊息重貼
        await self._post_sticky(message.channel)


async def setup(bot):
    await bot.add_cog(StickyCog(bot))
