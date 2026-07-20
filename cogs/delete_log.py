"""
cogs/delete_log.py
監控指定頻道（預設全伺服器）的訊息刪除事件，並記錄到指定日誌頻道。
指令：/刪除訊息紀錄  (guild_only, 管理員)
"""

import discord
from discord import app_commands
from discord.ext import commands
from utils.config import config_manager


# ─────────────────── 設定面板 ───────────────────

class LogChannelModal(discord.ui.Modal, title="設定日誌頻道"):
    """讓使用者輸入頻道 ID 作為日誌頻道"""

    channel_id = discord.ui.TextInput(
        label="日誌頻道 ID（輸入頻道 ID 或留空用目前頻道）",
        placeholder="例如：1234567890123456789",
        required=False,
        max_length=25,
    )

    def __init__(self, cog: "DeleteLogCog"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.channel_id.value.strip()
        if raw == "":
            ch = interaction.channel
        else:
            if not raw.isdigit():
                return await interaction.response.send_message("❌ 請輸入有效的頻道 ID（純數字）", ephemeral=True)
            ch = interaction.guild.get_channel(int(raw))
            if ch is None:
                return await interaction.response.send_message("❌ 找不到該頻道，請確認 ID 是否正確", ephemeral=True)

        config_manager.set_guild_setting(interaction.guild_id, "delete_log_channel", str(ch.id))
        await interaction.response.send_message(
            f"✅ 日誌頻道已設定為 {ch.mention}", ephemeral=True
        )
        # 更新面板
        view = DeleteLogPanelView(self.cog, interaction.guild_id)
        await interaction.followup.send(embed=view.build_embed(interaction.guild), view=view, ephemeral=True)


class MonitorChannelModal(discord.ui.Modal, title="設定監控頻道"):
    """讓使用者輸入要監控的頻道 ID（逗號分隔，留空 = 全伺服器）"""

    channel_ids = discord.ui.TextInput(
        label="監控頻道 ID（逗號分隔，留空代表全伺服器）",
        placeholder="例如：111... , 222...  或留空",
        required=False,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, cog: "DeleteLogCog"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.channel_ids.value.strip()
        if raw == "":
            ids = []  # 空 = 全伺服器
            msg = "✅ 監控範圍已設定為 **整個伺服器**"
        else:
            parts = [p.strip() for p in raw.replace("，", ",").split(",") if p.strip()]
            invalid = [p for p in parts if not p.isdigit()]
            if invalid:
                return await interaction.response.send_message(
                    f"❌ 以下不是有效的頻道 ID：`{'、'.join(invalid)}`", ephemeral=True
                )
            # 驗證頻道存在
            channels = []
            not_found = []
            for cid in parts:
                ch = interaction.guild.get_channel(int(cid))
                if ch:
                    channels.append(ch)
                else:
                    not_found.append(cid)
            if not_found:
                return await interaction.response.send_message(
                    f"❌ 找不到以下頻道 ID：`{'、'.join(not_found)}`", ephemeral=True
                )
            ids = [str(c.id) for c in channels]
            names = "、".join(c.mention for c in channels)
            msg = f"✅ 監控頻道已設定為：{names}"

        config_manager.set_guild_setting(interaction.guild_id, "delete_log_monitor", ids)
        await interaction.response.send_message(msg, ephemeral=True)
        view = DeleteLogPanelView(self.cog, interaction.guild_id)
        await interaction.followup.send(embed=view.build_embed(interaction.guild), view=view, ephemeral=True)


class DeleteLogPanelView(discord.ui.View):
    """主控面板"""

    def __init__(self, cog: "DeleteLogCog", guild_id: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id
        settings = config_manager.get_guild_settings(guild_id)
        # 根據目前啟用狀態決定按鈕樣式
        enabled = settings.get("delete_log_enabled", False)
        self.toggle_btn.style = discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success
        self.toggle_btn.label = "🔴 關閉監控" if enabled else "🟢 開啟監控"

    def build_embed(self, guild: discord.Guild) -> discord.Embed:
        settings = config_manager.get_guild_settings(guild.id)
        enabled = settings.get("delete_log_enabled", False)
        log_ch_id = settings.get("delete_log_channel")
        monitor_ids = settings.get("delete_log_monitor", [])

        log_ch = guild.get_channel(int(log_ch_id)) if log_ch_id else None
        if monitor_ids:
            monitor_str = "\n".join(
                f"• <#{cid}>" for cid in monitor_ids
                if guild.get_channel(int(cid))
            ) or "（頻道已刪除）"
        else:
            monitor_str = "📡 整個伺服器"

        embed = discord.Embed(
            title="🗑️ 刪除訊息紀錄 設定面板",
            color=0x2ECC71 if enabled else 0x95A5A6,
        )
        embed.add_field(
            name="狀態",
            value="🟢 **啟用中**" if enabled else "🔴 **未啟用**",
            inline=True,
        )
        embed.add_field(
            name="日誌頻道",
            value=log_ch.mention if log_ch else "⚠️ 尚未設定",
            inline=True,
        )
        embed.add_field(name="監控範圍", value=monitor_str, inline=False)
        embed.set_footer(text="提示：必須先設定日誌頻道才能開啟監控")
        return embed

    @discord.ui.button(label="📋 設定日誌頻道", style=discord.ButtonStyle.primary, row=0)
    async def set_log_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LogChannelModal(self.cog))

    @discord.ui.button(label="🔍 設定監控頻道", style=discord.ButtonStyle.secondary, row=0)
    async def set_monitor_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MonitorChannelModal(self.cog))

    @discord.ui.button(label="📡 監控整個伺服器", style=discord.ButtonStyle.secondary, row=0)
    async def monitor_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        config_manager.set_guild_setting(interaction.guild_id, "delete_log_monitor", [])
        await interaction.response.send_message("✅ 監控範圍已重設為 **整個伺服器**", ephemeral=True)
        view = DeleteLogPanelView(self.cog, interaction.guild_id)
        await interaction.followup.send(embed=view.build_embed(interaction.guild), view=view, ephemeral=True)

    @discord.ui.button(label="🟢 開啟監控", style=discord.ButtonStyle.success, row=1)
    async def toggle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = config_manager.get_guild_settings(interaction.guild_id)
        enabled = settings.get("delete_log_enabled", False)
        log_ch_id = settings.get("delete_log_channel")

        if not enabled and not log_ch_id:
            return await interaction.response.send_message(
                "❌ 請先設定日誌頻道再開啟監控！", ephemeral=True
            )

        new_state = not enabled
        config_manager.set_guild_setting(interaction.guild_id, "delete_log_enabled", new_state)
        msg = "🟢 刪除訊息紀錄已**開啟**！" if new_state else "🔴 刪除訊息紀錄已**關閉**。"
        await interaction.response.send_message(msg, ephemeral=True)
        view = DeleteLogPanelView(self.cog, interaction.guild_id)
        await interaction.edit_original_response(embed=view.build_embed(interaction.guild), view=view)


# ─────────────────── Cog ───────────────────

class DeleteLogCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── 指令 ──────────────────────────────────
    @app_commands.command(name="刪除訊息紀錄", description="設定伺服器刪除訊息的日誌功能")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def delete_log_panel(self, interaction: discord.Interaction):
        view = DeleteLogPanelView(self, interaction.guild_id)
        embed = view.build_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ── 事件監聽 ──────────────────────────────
    async def _get_log_channel(self, guild: discord.Guild):
        settings = config_manager.get_guild_settings(guild.id)
        if not settings.get("delete_log_enabled", False):
            return None
        ch_id = settings.get("delete_log_channel")
        return guild.get_channel(int(ch_id)) if ch_id else None

    def _in_monitor(self, guild_id: int, channel_id: int) -> bool:
        ids = config_manager.get_guild_settings(guild_id).get("delete_log_monitor", [])
        return not ids or str(channel_id) in ids

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if not self._in_monitor(message.guild.id, message.channel.id):
            return
        log_ch = await self._get_log_channel(message.guild)
        if not log_ch:
            return

        embed = discord.Embed(title="🗑️ 訊息已刪除", color=0xE74C3C, timestamp=message.created_at)
        embed.set_author(name=f"{message.author} ({message.author.id})", icon_url=message.author.display_avatar.url)
        embed.add_field(name="頻道", value=message.channel.mention, inline=True)
        content = (message.content or "*(無文字內容)*")[:1024]
        embed.add_field(name="內容", value=content, inline=False)
        if message.attachments:
            embed.add_field(name="附件", value="\n".join(a.filename for a in message.attachments), inline=False)
        embed.set_footer(text=f"訊息 ID: {message.id}")
        try:
            await log_ch.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return  # 只有 embed 更新，忽略
        if not self._in_monitor(before.guild.id, before.channel.id):
            return
        log_ch = await self._get_log_channel(before.guild)
        if not log_ch:
            return

        embed = discord.Embed(title="✏️ 訊息已編輯", color=0xF39C12, timestamp=after.edited_at or after.created_at)
        embed.set_author(name=f"{before.author} ({before.author.id})", icon_url=before.author.display_avatar.url)
        embed.add_field(name="頻道", value=before.channel.mention, inline=True)
        embed.add_field(name="跳轉", value=f"[點此]({after.jump_url})", inline=True)
        embed.add_field(name="修改前", value=(before.content or "*(空)*")[:1024], inline=False)
        embed.add_field(name="修改後", value=(after.content or "*(空)*")[:1024], inline=False)
        embed.set_footer(text=f"訊息 ID: {before.id}")
        try:
            await log_ch.send(embed=embed)
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(DeleteLogCog(bot))
