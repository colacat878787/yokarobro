"""
cogs/starboard.py
星板系統 (Starboard)
自動將熱門訊息轉發到指定頻道。
指令：
  !starboard set #頻道 [門檻]  - 設定星板頻道 (預設門檻: 3)
  !starboard off               - 關閉星板功能
"""

import discord
from discord.ext import commands
import json
import os
from utils.config import config_manager

STAR_FILE = "starboard_cache.json"


class StarboardCog(commands.Cog):
    """星板系統 - 自動轉發熱門訊息"""

    def __init__(self, bot):
        self.bot = bot
        self.starred_messages = self._load_starred()

    def _load_starred(self):
        if os.path.exists(STAR_FILE):
            try:
                with open(STAR_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_starred(self):
        with open(STAR_FILE, "w", encoding="utf-8") as f:
            json.dump(self.starred_messages, f, ensure_ascii=False, indent=2)

    @commands.group(name="starboard", aliases=["星板", "star"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def starboard(self, ctx):
        """星板系統主指令"""
        settings = config_manager.get_guild_settings(ctx.guild.id)
        enabled = settings.get("starboard_enabled", False)
        if enabled:
            ch_id = settings.get("starboard_channel")
            threshold = settings.get("starboard_threshold", 3)
            channel = ctx.guild.get_channel(int(ch_id)) if ch_id else None
            ch_str = channel.mention if channel else "未設定"
            await ctx.send(f"✅ 星板功能已開啟\n頻道：{ch_str}\n門檻：{threshold} 顆星")
        else:
            await ctx.send("❌ 星板功能尚未開啟。\n使用 `!starboard set #頻道 [門檻]` 來設定。")

    @starboard.command(name="set", aliases=["設定", "setup"])
    @commands.has_permissions(administrator=True)
    async def starboard_set(self, ctx, channel: discord.TextChannel = None, threshold: int = 3):
        """設定星板頻道"""
        if channel is None:
            channel = ctx.channel
        if threshold < 1:
            threshold = 1
        if threshold > 20:
            await ctx.send("❌ 門檻不能超過 20 喔！", ephemeral=True)
            return
        config_manager.set_guild_setting(ctx.guild.id, "starboard_enabled", True)
        config_manager.set_guild_setting(ctx.guild.id, "starboard_channel", str(channel.id))
        config_manager.set_guild_setting(ctx.guild.id, "starboard_threshold", threshold)
        embed = discord.Embed(title="✅ 星板功能已開啟", color=0xf1c40f)
        embed.add_field(name="📺 頻道", value=channel.mention, inline=True)
        embed.add_field(name="⭐ 門檻", value=f"{threshold} 顆星", inline=True)
        embed.set_footer(text="當訊息獲得足夠多的星星反應時，會自動轉發到這個頻道")
        await ctx.send(embed=embed)

    @starboard.command(name="off", aliases=["關閉", "disable"])
    @commands.has_permissions(administrator=True)
    async def starboard_off(self, ctx):
        """關閉星板功能"""
        config_manager.set_guild_setting(ctx.guild.id, "starboard_enabled", False)
        await ctx.send("✅ 星板功能已關閉！")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        emoji_name = payload.emoji.name if payload.emoji.id else str(payload.emoji)
        is_star = emoji_name in ("⭐", "🌟", "✨")
        if not is_star:
            return
        settings = config_manager.get_guild_settings(payload.guild_id)
        if not settings.get("starboard_enabled", False):
            return
        threshold = settings.get("starboard_threshold", 3)
        channel_id = settings.get("starboard_channel")
        if not channel_id:
            return
        starboard_channel = self.bot.get_channel(int(channel_id))
        if not starboard_channel:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        try:
            message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden):
            return

        # 計算總星數
        total_stars = 0
        for reaction in message.reactions:
            r_emoji = reaction.emoji
            r_name = r_emoji.name if hasattr(r_emoji, "name") else str(r_emoji)
            if r_name in ("⭐", "🌟", "✨"):
                total_stars += reaction.count
        if total_stars < threshold:
            return

        # 檢查是否已經星板過
        msg_key = f"{payload.channel_id}:{payload.message_id}"
        if msg_key in self.starred_messages:
            existing_msg_id = self.starred_messages[msg_key]
            try:
                existing_msg = await starboard_channel.fetch_message(existing_msg_id)
                embed = existing_msg.embeds[0] if existing_msg.embeds else None
                if embed:
                    for field in embed.fields:
                        if field.name == "⭐ 星數":
                            field.value = str(total_stars)
                    try:
                        await existing_msg.edit(embed=embed)
                    except:
                        pass
            except (discord.NotFound, discord.Forbidden):
                self.starred_messages.pop(msg_key, None)
                await self._create_starboard_message(message, starboard_channel, total_stars)
            return

        await self._create_starboard_message(message, starboard_channel, total_stars)

    async def _create_starboard_message(self, message: discord.Message, channel: discord.TextChannel, star_count: int):
        """建立星板訊息"""
        embed = discord.Embed(
            description=message.content[:1024] if message.content else "*（此訊息沒有文字內容）*",
            color=0xf1c40f,
            timestamp=message.created_at
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )
        embed.add_field(name="📝 原始訊息", value=f"[點擊查看]({message.jump_url})", inline=False)
        embed.add_field(name="⭐ 星數", value=str(star_count), inline=True)
        embed.add_field(name="📺 來源頻道", value=message.channel.mention, inline=True)
        if message.embeds:
            embed.add_field(name="⚠️ 注意", value="原文包含 embed，請查看原始訊息", inline=False)
        if message.attachments:
            try:
                file = await message.attachments[0].to_file()
                sent = await channel.send(file=file, embed=embed)
            except:
                sent = await channel.send(embed=embed)
        else:
            sent = await channel.send(embed=embed)
        msg_key = f"{message.channel.id}:{message.id}"
        self.starred_messages[msg_key] = sent.id
        self._save_starred()


async def setup(bot):
    await bot.add_cog(StarboardCog(bot))
