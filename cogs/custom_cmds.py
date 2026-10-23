"""
cogs/custom_cmds.py
自訂指令系統
讓管理員自訂「!名稱 → 回應」，不用改程式碼。

指令：
  !新增指令 <名稱> <回應內容>   - 新增/修改自訂指令（可含 {user} / {server} / {channel}）
  !刪除指令 <名稱>              - 刪除
  !指令列表                    - 列出本伺服器的自訂指令
資料存 data/custom_commands.json。
"""

import discord
from discord.ext import commands

from utils.data_store import DataStore


def _apply_placeholders(content: str, message: discord.Message) -> str:
    return (content
            .replace("{user}", message.author.mention)
            .replace("{username}", message.author.display_name)
            .replace("{server}", message.guild.name)
            .replace("{channel}", message.channel.mention))


class CustomCmdsCog(commands.Cog):
    """🧩 自訂指令系統"""

    def __init__(self, bot):
        self.bot = bot
        # {guild_id: {name: {"content": str, "created_by": int}}}
        self.store = DataStore("custom_commands.json")

    # ===== 指令：新增 =====
    @commands.command(name="新增指令", aliases=["addcmd", "customcmd"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(send_messages=True)
    async def add_cmd(self, ctx, name: str = None, *, content: str = None):
        """新增自訂指令：!新增指令 <名稱> <回應>"""
        if not name or not content:
            await ctx.send(
                "🧩 **自訂指令用法**\n"
                "`!新增指令 規則 本群規則請看公告頻道！`\n\n"
                "回應中可用的佔位符：\n"
                "• `{user}`＝發言者\n• `{username}`＝顯示名稱\n• `{server}`＝伺服器名\n• `{channel}`＝頻道"
            )
            return
        name = name.lower().lstrip("!")
        if self.bot.get_command(name):
            await ctx.send(f"❌ `{name}` 已是機器人的內建指令或別名，換個名字！")
            return
        if not name.isalnum() and not all(ch.isalnum() or "\u4e00" <= ch <= "\u9fff" for ch in name):
            await ctx.send("❌ 指令名稱請使用英數字或中文。")
            return

        guild_cmds = self.store.get(ctx.guild.id, {})
        created = name in guild_cmds
        guild_cmds[name] = {"content": content, "created_by": ctx.author.id}
        self.store.set(ctx.guild.id, guild_cmds)
        await ctx.send(f"✅ 已{'更新' if created else '新增'}自訂指令：`!{name}`\n試試看：`!{name}`")

    # ===== 指令：刪除 =====
    @commands.command(name="刪除指令", aliases=["delcmd", "removecmd"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def del_cmd(self, ctx, name: str = None):
        """刪除自訂指令：!刪除指令 <名稱>"""
        if not name:
            await ctx.send("❌ 請提供要刪除的指令名稱。")
            return
        guild_cmds = self.store.get(ctx.guild.id, {})
        if name.lower() not in guild_cmds:
            await ctx.send(f"❌ 找不到自訂指令 `{name}`。")
            return
        guild_cmds.pop(name.lower())
        self.store.set(ctx.guild.id, guild_cmds)
        await ctx.send(f"✅ 已刪除自訂指令 `{name}`。")

    # ===== 指令：清單 =====
    @commands.command(name="指令列表", aliases=["customcmds"])
    @commands.guild_only()
    async def cmd_list(self, ctx):
        """列出本伺服器的自訂指令"""
        guild_cmds = self.store.get(ctx.guild.id, {})
        if not guild_cmds:
            await ctx.send("📋 本伺服器還沒有任何自訂指令。使用 `!新增指令 <名稱> <回應>` 來新增！")
            return
        lines = [f"• `!{name}` — {data['content'][:50]}" for name, data in list(guild_cmds.items())[:25]]
        embed = discord.Embed(
            title=f"🧩 自訂指令（{len(guild_cmds)}）",
            description="\n".join(lines),
            color=0x2ECC71,
        )
        await ctx.send(embed=embed)

    # ===== 監聽：回覆自訂指令 =====
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        prefix = await self.bot.get_prefix(message)
        if not message.content.startswith(prefix):
            return
        name = message.content[len(prefix):].strip().split()[0].lower()
        if not name:
            return
        if self.bot.get_command(name):
            return  # 內建指令優先

        guild_cmds = self.store.get(message.guild.id, {})
        data = guild_cmds.get(name)
        if not data:
            return
        content = _apply_placeholders(data["content"], message)
        try:
            await message.channel.send(content)
        except (discord.Forbidden, discord.NotFound):
            pass


async def setup(bot):
    await bot.add_cog(CustomCmdsCog(bot))
