"""
cogs/voice_invite.py
語音頻道邀請系統（私訊觸發）
使用者把「語音頻道的邀請連結」私訊給機器人，機器人會解析邀請：
- 找到邀請指向的伺服器、語音頻道
- 機器人在那個伺服器 → 自動加入該語音頻道，並私訊告知
- 機器人不在那個伺服器 → 也會私訊告知

範例 DM：https://discord.gg/xxxx（在語音頻道按「邀請」建立的連結會自動帶頻道）
"""

import re

import discord
from discord.ext import commands

from utils.data_store import DataStore

INVITE_REGEX = re.compile(r"(?:discord\.gg|discord(?:app)?\.com/invite)/([A-Za-z0-9-]{2,20})")


class VoiceInviteCog(commands.Cog):
    """📬 私訊語音邀請 → 機器人自動加入"""

    def __init__(self, bot):
        self.bot = bot
        # 存檔讓 voice_reconnect 知道最近被邀請去的頻道 {guild_id: channel_id}
        self.store = DataStore("voice_invite.json")
        # 避免同一個使用者短時間狂發邀請 {user_id: timestamp}
        self._cooldowns = {}

    def cog_unload(self):
        pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is not None:
            return  # 只處理私訊
        content = message.content or ""
        match = INVITE_REGEX.search(content)
        if not match:
            return

        code = match.group(1)
        # 冷卻：同一人 10 秒內狂發只處理一次
        import time
        now = time.time()
        last = self._cooldowns.get(message.author.id, 0)
        if now - last < 10:
            return
        self._cooldowns[message.author.id] = now

        # 解析邀請
        try:
            invite = await self.bot.fetch_invite(code, with_counts=True)
        except discord.NotFound:
            await self._dm_reply(message, "❌ 這個邀請連結已失效了嗷～")
            return
        except discord.HTTPException as e:
            await self._dm_reply(message, f"❌ 無法解析邀請連結：{e}")
            return

        invite_guild = invite.guild
        if not invite_guild:
            await self._dm_reply(message, "❌ 這個邀請連結讀不到伺服器資訊。")
            return

        bot_guild = self.bot.get_guild(invite_guild.id)
        if bot_guild is None:
            # 機器人不在那個伺服器
            await self._dm_reply(
                message,
                f"🐾 嗷～我**不在「{invite_guild.name}」**的伺服器裡！\n"
                f"想讓我先加入的話，請先把我邀請進去（需要「連接語音頻道」權限），\n"
                f"然後再把語音頻道的邀請連結發一次給我就好啦！",
            )
            return

        channel = invite.channel
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            await self._dm_reply(
                message,
                "📨 這個邀請指向的**不是語音頻道**。\n"
                "請在**語音頻道**上按「邀請」建立連結，我才知道要加入哪裡！",
            )
            return

        # 權限檢查
        perms = channel.permissions_for(bot_guild.me)
        if not (perms.view_channel and perms.connect):
            await self._dm_reply(
                message,
                f"❌ 我在「{bot_guild.name}」沒有連接 `{channel.name}` 的權限。\n"
                "請請管理員給我「連接語音頻道」的權限再試一次！",
            )
            return

        try:
            existing = bot_guild.voice_client
            if existing and existing.is_connected():
                if existing.channel.id == channel.id:
                    await self._dm_reply(message, f"🐾 我已經在 `{channel.name}` 裡了嗷嗷～不用邀請我也是會配合的！")
                    return
                await existing.move_to(channel)
            else:
                await channel.connect(timeout=60, self_deaf=True)
        except Exception as e:
            await self._dm_reply(message, f"❌ 加入 `{channel.name}` 失敗：{e}")
            return

        # 成功：記錄（讓 !重回語音 / 重啟重連可以找回來）
        vrc = self.bot.get_cog("VoiceReconnectCog")
        if vrc:
            vrc.store.set(bot_guild.id, channel.id)
        else:
            self.store.set(bot_guild.id, channel.id)
        await self._dm_reply(
            message,
            f"✅ 嗷嗷！收到你的邀請，我加入「{bot_guild.name}」的 **`{channel.name}`** 了！\n"
            "（我會安靜待著，不會亂放音樂！）",
        )

    async def _dm_reply(self, message: discord.Message, text: str):
        try:
            await message.author.send(text)
        except discord.Forbidden:
            pass
