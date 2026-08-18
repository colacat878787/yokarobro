"""
cogs/auto_role.py
自動身分組系統 (Auto-Role)
新成員加入時自動分配身分組。
指令：
  !autorole set @身分組    - 設定自動身分組
  !autorole off            - 關閉自動身分組
  !autorole status         - 查看當前設定
"""

import discord
from discord.ext import commands
import json
import os
from utils.config import config_manager


class AutoRoleCog(commands.Cog):
    """自動身分組系統 - 新成員加入時自動分配身分組"""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="autorole", aliases=["自動身分組", "ar"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def autorole(self, ctx):
        """自動身分組系統主指令"""
        settings = config_manager.get_guild_settings(ctx.guild.id)
        role_id = settings.get("auto_role_id")
        enabled = settings.get("auto_role_enabled", False)

        if enabled and role_id:
            role = ctx.guild.get_role(int(role_id))
            if role:
                await ctx.send(f"✅ 自動身分組功能已開啟\n身分組：{role.mention} ({role.name})\n使用 `!autorole off` 關閉")
            else:
                await ctx.send("⚠️ 設定的身分組已不存在，請重新設定！")
        else:
            await ctx.send("❌ 自動身分組尚未設定\n使用 `!autorole set @身分組` 來設定。")

    @autorole.command(name="set", aliases=["設定", "設置"])
    @commands.has_permissions(administrator=True)
    async def autorole_set(self, ctx, role: discord.Role):
        """設定自動身分組"""
        # 檢查 bot 權限
        if not ctx.guild.me.guild_permissions.manage_roles:
            await ctx.send("❌ 我需要管理身分組權限才能設定自動身分組！", ephemeral=True)
            return

        # 檢查身分組等級
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ 我的身分組等級不足，無法給予這個身分組！", ephemeral=True)
            return

        if role.is_default():
            await ctx.send("❌ 不能將 `@everyone` 當作自動身分組！", ephemeral=True)
            return

        config_manager.set_guild_setting(ctx.guild.id, "auto_role_enabled", True)
        config_manager.set_guild_setting(ctx.guild.id, "auto_role_id", str(role.id))

        embed = discord.Embed(title="✅ 自動身分組設定完成", color=0x2ecc71)
        embed.add_field(name="🏷️ 身分組", value=f"{role.mention} ({role.name})", inline=False)
        embed.add_field(name="📝 功能", value="當新成員加入伺服器時，會自動獲得此身分組。", inline=False)
        embed.set_footer(text="使用 !autorole off 來關閉")
        await ctx.send(embed=embed)

    @autorole.command(name="off", aliases=["關閉", "disable"])
    @commands.has_permissions(administrator=True)
    async def autorole_off(self, ctx):
        """關閉自動身分組"""
        config_manager.set_guild_setting(ctx.guild.id, "auto_role_enabled", False)
        await ctx.send("✅ 自動身分組功能已關閉！")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """新成員加入時自動分配身分組"""
        settings = config_manager.get_guild_settings(member.guild.id)
        if not settings.get("auto_role_enabled", False):
            return

        role_id = settings.get("auto_role_id")
        if not role_id:
            return

        role = member.guild.get_role(int(role_id))
        if not role:
            return

        try:
            await member.add_roles(role, reason="自動身分組")
        except discord.Forbidden:
            print(f"[AutoRole] 無法給予身分組到 {member}：權限不足")
        except Exception as e:
            print(f"[AutoRole] 給予身分組失敗: {e}")


async def setup(bot):
    await bot.add_cog(AutoRoleCog(bot))
