"""
cogs/voice_reconnect.py
語音重連系統
- 機器人重啟（!reboot、自動更新、關機）時：停止音訊播放、離開語音頻道，
  並記住當時所在的語音頻道
- 重啟完成後自動重新進入上次的語音頻道（不繼續播放音樂）
指令：
  !重回語音  - 手動立刻照存檔重新加入語音頻道
資料存 data/voice_reconnect.json
"""

import asyncio

import discord
from discord.ext import commands

from utils.data_store import DataStore


class VoiceReconnectCog(commands.Cog):
    """🔊 重啟後重回語音頻道"""

    def __init__(self, bot):
        self.bot = bot
        # {guild_id: channel_id}
        self.store = DataStore("voice_reconnect.json")
        self._closed = False
        self._shutting_down = False
        # 攔截 bot.close()：任何 graceful 關閉前先乾淨離開語音
        self._orig_close = bot.close
        bot.close = self._wrapped_close

    def cog_unload(self):
        # 還原 close（reload 時不重複包裹）
        if getattr(self.bot, "close", None) is self._wrapped_close:
            self.bot.close = self._orig_close

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """隨時記錄機器人所在的語音頻道（含被 o._exit 硬重啟前的狀態）"""
        if member.id != self.bot.user.id:
            return
        guild = member.guild
        if not guild:
            return
        if after.channel:
            # 被踢進 Stage 上台這種狀態也算，先記頻道
            if not self._shutting_down:
                self.store.set(guild.id, after.channel.id)
        elif before.channel and not self._shutting_down:
            # 主動離開（管理員踢出、!stop 離開等）→ 清掉記錄，重啟後不會誤重返虎口
            self.store.delete(guild.id)

    # ===== 關閉攔截 =====
    async def _wrapped_close(self, *args, **kwargs):
        try:
            await asyncio.wait_for(self.save_and_leave_all(), timeout=15)
        except Exception as e:
            print(f"[VoiceReconnect] 關閉前清理失敗: {e}")
        return await self._orig_close(*args, **kwargs)

    async def save_and_leave_all(self):
        """記住所有語音所在的頻道、停播、乾淨離開"""
        self._shutting_down = True
        for vc in list(self.bot.voice_clients):
            try:
                if not vc.is_connected():
                    continue
                guild, channel = vc.guild, vc.channel
                if guild is not None and isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                    self.store.set(guild.id, channel.id)
                    print(f"[VoiceReconnect] 已記住 {guild.name} → {channel.name}")
                if vc.is_playing() or vc.is_paused():
                    vc.stop()
                await vc.disconnect()
            except Exception as e:
                print(f"[VoiceReconnect] 離開語音時出錯（{guild.name if guild else '?'}）: {e}")

    # ===== 開機後自動重回 =====
    @commands.Cog.listener()
    async def on_ready(self):
        if self._closed:
            return
        await self._rejoin_all()

    async def _rejoin_all(self):
        connected = 0
        for guild_id_str in list(self.store.data.keys()):
            guild = self.bot.get_guild(int(guild_id_str))
            if guild is None:
                self.store.delete(guild_id_str)  # 已不在那個伺服器
                continue
            for vc in self.bot.voice_clients:
                if vc.guild and vc.guild.id == guild.id and vc.is_connected():
                    break
            else:
                channel_id = self.store.get(guild_id_str)
                channel = guild.get_channel(int(channel_id)) if channel_id else None
                if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                    self.store.delete(guild_id_str)  # 頻道不存在了
                    continue
                perms = channel.permissions_for(guild.me)
                if not (perms.view_channel and perms.connect):
                    print(f"[VoiceReconnect] 沒有權限重進 {guild.name}/{channel.name}，跳過")
                    continue
                try:
                    await channel.connect(timeout=60, self_deaf=True)
                    connected += 1
                    print(f"[VoiceReconnect] 已重回 {guild.name} 的 {channel.name}（不播放音樂）")
                except Exception as e:
                    print(f"[VoiceReconnect] 重進 {guild.name}/{channel.name} 失敗: {e}")

    # ===== 手動重連指令 =====
    @commands.command(name="重回語音", aliases=["rejoinvoice", "語音重連"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def rejoin_voice(self, ctx):
        """手動照存檔重新加入語音頻道：!重回語音"""
        target = self.store.get(ctx.guild.id)
        channel = ctx.guild.get_channel(int(target)) if target else None
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            await ctx.send("📌 存檔裡沒有本伺服器的語音頻道（可能上次重啟時bot不在語音裡）。")
            return
        try:
            if ctx.voice_client:
                if ctx.voice_client.channel.id == channel.id:
                    await ctx.send(f"🐾 我已經在 `{channel.name}` 裡了嗷～")
                    return
                await ctx.voice_client.move_to(channel)
            else:
                await channel.connect(timeout=60, self_deaf=True)
            self.store.set(ctx.guild.id, channel.id)
            await ctx.send(f"✅ 已回到 `{channel.name}`！（不會自動恢復播放，要用 `!play` 再播放）")
        except Exception as e:
            await ctx.send(f"❌ 重進語音失敗：{e}")


async def setup(bot):
    await bot.add_cog(VoiceReconnectCog(bot))
