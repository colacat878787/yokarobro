"""
cogs/reaction_roles.py
反應角色系統 (Reaction Roles)
讓用戶透過點擊訊息的反應來自分配身分組。
指令：
  !reactionrole setup <訊息ID> <表情> @身分組 - 為訊息新增反應角色
  !reactionrole list  - 列出所有反應角色
  !reactionrole delete <訊息ID> - 刪除反應角色設定
"""

import discord
from discord.ext import commands
import re
from utils.data_store import DataStore

rr_store = DataStore("reaction_roles.json")


class ReactionRolesCog(commands.Cog):
    """反應角色系統 - 讓用戶透過點擊反應來獲取身分組"""

    def __init__(self, bot):
        self.bot = bot

    def _get_guild_data(self, guild_id: int) -> dict:
        data = rr_store.get(str(guild_id), {})
        return data if isinstance(data, dict) else {}

    def _save_guild_data(self, guild_id: int, data: dict):
        all_data = rr_store.get_all()
        all_data[str(guild_id)] = data
        rr_store.save()

    def _resolve_emoji(self, guild: discord.Guild, emoji_str: str):
        """解析表情字串為 discord emoji 或 str"""
        emoji_str = emoji_str.strip()
        # 標準 Unicode 表情
        if emoji_str.startswith("<") and emoji_str.endswith(">"):
            match = re.match(r'<:\w+:(\d+)>', emoji_str)
            if match:
                emoji = guild.get_emoji(int(match.group(1)))
                if emoji:
                    return emoji
        # 嘗試 :name:id 格式
        match = re.match(r'^(\w+):(\d+)$', emoji_str)
        if match:
            emoji = guild.get_emoji(int(match.group(2)))
            if emoji:
                return emoji
        # 嘗試 :name: 格式
        match = re.match(r'^:(\w+):$', emoji_str)
        if match:
            for e in guild.emojis:
                if e.name == match.group(1):
                    return e
        # Unicode 表情
        if len(emoji_str) <= 4:
            return emoji_str
        return None



    @commands.hybrid_group(name="reactionrole", aliases=["rr", "反應角色"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def reaction_role(self, ctx, message: discord.Message = None, emoji: str = None, role: discord.Role = None):
        """設定反應角色 - 讓用戶點擊反應自動獲取身分組"""
        if message is None:
            await ctx.send("❓ 請回覆要設定反應角色的訊息，或指定訊息 ID。\n範例：`!rr <訊息ID> <表情> @身分組`", ephemeral=True)
            return
        if message.guild != ctx.guild:
            await ctx.send("❌ 只能設定本伺服器的訊息喔！", ephemeral=True)
            return
        resolved_emoji = self._resolve_emoji(ctx.guild, emoji)
        if resolved_emoji is None:
            await ctx.send("❌ 無法識別的表情！請使用標準表情或 `<:name:id>` 格式的自訂表情。", ephemeral=True)
            return

        guild_id = str(ctx.guild.id)
        data = self._get_guild_data(ctx.guild.id)
        msg_key = f"{message.channel.id}:{message.id}"
        if msg_key not in data:
            data[msg_key] = {"message_id": message.id, "channel_id": message.channel.id, "roles": {}}
        emoji_str = str(resolved_emoji)
        data[msg_key]["roles"][emoji_str] = role.id
        self._save_guild_data(ctx.guild.id, data)

        try:
            await message.add_reaction(resolved_emoji)
        except (discord.Forbidden, discord.HTTPException):
            pass

        embed = discord.Embed(title="✅ 反應角色設定完成", color=0x2ecc71)
        embed.add_field(name="📝 訊息", value=f"[點擊查看]({message.jump_url})", inline=False)
        embed.add_field(name="😀 表情", value=str(resolved_emoji), inline=True)
        embed.add_field(name="🏷️ 身分組", value=f"{role.mention} (`{role.name}`)", inline=True)
        embed.set_footer(text="用戶點擊該表情即可自動取得身分組")
        await ctx.send(embed=embed)

    @reaction_role.command(name="list", aliases=["列表"])
    @commands.has_permissions(manage_roles=True)
    async def rr_list(self, ctx):
        """列出伺服器的所有反應角色"""
        data = self._get_guild_data(ctx.guild.id)
        if not data:
            await ctx.send("📭 目前伺服器沒有設定任何反應角色。", ephemeral=True)
            return
        embed = discord.Embed(title="📋 伺服器反應角色列表", color=0x3498db)
        count = 0
        for msg_key, msg_data in data.items():
            roles = msg_data.get("roles", {})
            if not roles:
                continue
            channel = ctx.guild.get_channel(msg_data.get("channel_id", 0))
            msg_id = msg_data.get("message_id", 0)
            ch_mention = channel.mention if channel else f"ID: {msg_data.get('channel_id')}"
            jump_url = f"https://discord.com/channels/{ctx.guild.id}/{msg_data.get('channel_id',0)}/{msg_id}"
            role_info = []
            for emoji_str, role_id in roles.items():
                role = ctx.guild.get_role(role_id)
                rn = role.mention if role else f"已刪除 ({role_id})"
                role_info.append(f"{emoji_str} {rn}")
            embed.add_field(name=f"#{count+1} {ch_mention}", value=f"[訊息]({jump_url})\n" + "\n".join(role_info), inline=False)
            count += 1
        embed.set_footer(text=f"共 {count} 個反應角色設定")
        await ctx.send(embed=embed)

    @reaction_role.command(name="delete", aliases=["刪除"])
    @commands.has_permissions(manage_roles=True)
    async def rr_delete(self, ctx, message_id: int):
        """刪除指定訊息的所有反應角色設定"""
        guild_id = str(ctx.guild.id)
        data = self._get_guild_data(ctx.guild.id)
        found = False
        to_delete = []
        for msg_key, msg_data in data.items():
            if str(msg_data.get("message_id")) == str(message_id):
                to_delete.append(msg_key)
                found = True
        if not found:
            await ctx.send(f"❌ 沒有找到訊息 ID `{message_id}` 的反應角色設定。", ephemeral=True)
            return
        for key in to_delete:
            del data[key]
        self._save_guild_data(ctx.guild.id, data)
        try:
            msg = await ctx.channel.fetch_message(message_id)
            await msg.clear_reactions()
            await ctx.send(f"✅ 已刪除訊息 `{message_id}` 的反應角色設定並清除反應！")
        except Exception:
            await ctx.send(f"✅ 已刪除訊息 `{message_id}` 的反應角色設定！")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        data = self._get_guild_data(guild.id)
        msg_key = f"{payload.channel_id}:{payload.message_id}"
        msg_data = data.get(msg_key)
        if not msg_data:
            return
        roles = msg_data.get("roles", {})
        emoji_str = str(payload.emoji)
        role_id = roles.get(emoji_str)
        if role_id is None and payload.emoji.name:
            full_str = f"<:{payload.emoji.name}:{payload.emoji.id}>" if payload.emoji.id else str(payload.emoji)
            role_id = roles.get(full_str)
        if role_id is None:
            return
        member = guild.get_member(payload.user_id)
        if member is None:
            member = await guild.fetch_member(payload.user_id)
        role = guild.get_role(role_id)
        if role:
            if role in member.roles:
                try: await member.remove_roles(role, reason="反應角色切換")
                except discord.Forbidden: pass
            else:
                try: await member.add_roles(role, reason="反應角色")
                except discord.Forbidden: pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        data = self._get_guild_data(guild.id)
        msg_key = f"{payload.channel_id}:{payload.message_id}"
        msg_data = data.get(msg_key)
        if not msg_data:
            return
        roles = msg_data.get("roles", {})
        emoji_str = str(payload.emoji)
        role_id = roles.get(emoji_str)
        if role_id is None and payload.emoji.name:
            full_str = f"<:{payload.emoji.name}:{payload.emoji.id}>" if payload.emoji.id else str(payload.emoji)
            role_id = roles.get(full_str)
        if role_id is None:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return
        role = guild.get_role(role_id)
        if role and role in member.roles:
            try: await member.remove_roles(role, reason="反應角色移除")
            except discord.Forbidden: pass


async def setup(bot):
    await bot.add_cog(ReactionRolesCog(bot))
