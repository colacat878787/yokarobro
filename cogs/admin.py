import discord
from discord.ext import commands
from discord import app_commands
import os
import psutil
from utils.config import config_manager
OWNER_ID = 1113353915010920452
# --- Modals ---

class StringConfigModal(discord.ui.Modal):
    def __init__(self, title, key, current_val):
        super().__init__(title=title)
        self.key = key
        self.input = discord.ui.TextInput(
            label=f"修改 {key}",
            placeholder="請輸入新數值...",
            default=str(current_val) if current_val else "",
            required=True
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        config_manager.set_guild_setting(interaction.guild.id, self.key, self.input.value)
        await interaction.response.send_message(f"✅ 已成功將 `{self.key}` 修改為：`{self.input.value}`", ephemeral=True)

# --- Sub-Menus ---

class ModuleSettingsView(discord.ui.View):
    def __init__(self, bot, parent_view):
        super().__init__(timeout=60)
        self.bot = bot
        self.parent_view = parent_view
        self._update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        mgmt = self.bot.get_cog("ManagementCog")
        if mgmt and mgmt.is_high_admin(interaction.user.id):
            return True
        await interaction.response.send_message("❌ 這是高階管理面板，非受權者禁止操作！🐾", ephemeral=True)
        return False

    def _update_buttons(self):
        # 這裡動態判定模組狀態
        exts = {
            "cogs.ai": "AI 對話",
            "cogs.music": "音樂系統",
            "cogs.kuji": "一番賞系統",
            "cogs.security": "安全防護",
            "cogs.record": "錄影系統",
            "cogs.economy": "經濟系統"
        }
        self.clear_items()
        for path, name in exts.items():
            is_on = path in self.bot.extensions
            style = discord.ButtonStyle.success if is_on else discord.ButtonStyle.danger
            btn = discord.ui.Button(label=name, style=style, custom_id=f"toggle_{path}")
            btn.callback = self._create_callback(path, name)
            self.add_item(btn)
        
        # 回到主選單按鈕
        back_btn = discord.ui.Button(label="⬅️ 返回主選單", style=discord.ButtonStyle.secondary, row=4)
        back_btn.callback = self._back_to_main
        self.add_item(back_btn)

    def _create_callback(self, path, name):
        async def callback(interaction: discord.Interaction):
            try:
                if path in self.bot.extensions:
                    await self.bot.unload_extension(path)
                    msg = f"❌ 已關閉 {name}"
                else:
                    await self.bot.load_extension(path)
                    msg = f"✅ 已開啟 {name}"
                self._update_buttons()
                await interaction.response.edit_message(view=self)
                await interaction.followup.send(msg, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"⚠️ 操作失敗: {e}", ephemeral=True)
        return callback

    async def _back_to_main(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="🔧 請選擇你要修改的設定類別：", view=self.parent_view)

class ConfigSettingsView(discord.ui.View):
    def __init__(self, bot, parent_view, category):
        super().__init__(timeout=60)
        self.bot = bot
        self.parent_view = parent_view
        self.category = category
        self._setup_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != 1113353915010920452:
            await interaction.response.send_message("❌ 這是高階管理面板，非擁有者禁止操作！🐾", ephemeral=True)
            return False
        return True

    def _setup_buttons(self):
        # 根據類別顯示不同的設定按鈕
        self.clear_items()
        configs = []
        if self.category == "security":
            configs = [("驗證身分組名稱", "verify_role"), ("工作人員身分組", "staff_role")]
        elif self.category == "features":
            configs = [("XP 獲取倍率", "xp_rate")]
        elif self.category == "music_recommend":
            self._add_music_recommend_buttons()
            return
        
        # 重新設計按鈕加載邏輯以支援切換按鈕
        if self.category == "modmail":
            self._add_modmail_buttons()
        else:
            for label, key in configs:
                btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
                btn.callback = self._create_modal_callback(label, key)
                self.add_item(btn)

        back_btn = discord.ui.Button(label="⬅️ 返回主選單", style=discord.ButtonStyle.secondary, row=4)
        back_btn.callback = self._back_to_main
        self.add_item(back_btn)

    def _add_modmail_buttons(self):
        # 因為 View 需要知道 guild_id，我們稍後在 callback 中獲取
        btn_anon = discord.ui.Button(label="👤 切換匿名/實名模式", style=discord.ButtonStyle.primary)
        async def toggle_anon_callback(interaction: discord.Interaction):
            settings = config_manager.get_guild_settings(interaction.guild.id)
            current = settings.get("modmail_anonymous", True)
            config_manager.set_guild_setting(interaction.guild.id, "modmail_anonymous", not current)
            mode = "匿名" if not current else "實名 (顯示名字)"
            await interaction.response.send_message(f"✅ Modmail 模式已切換為：**{mode}**", ephemeral=True)
            
        btn_anon.callback = toggle_anon_callback
        self.add_item(btn_anon)

    def _add_music_recommend_buttons(self):
        # 1. 設置頻道按鈕
        btn_channel = discord.ui.Button(label="📍 設定此頻道為推薦頻道", style=discord.ButtonStyle.success)
        async def set_channel_callback(interaction: discord.Interaction):
            config_manager.set_guild_setting(interaction.guild.id, "recommend_channel", str(interaction.channel.id))
            await interaction.response.send_message(f"✅ 已成功將 {interaction.channel.mention} 設定為【音樂推薦頻道】！", ephemeral=True)
        btn_channel.callback = set_channel_callback
        self.add_item(btn_channel)

        # 2. 開關按鈕
        settings = config_manager.get_guild_settings(self.bot.get_guild(self.parent_view.bot.guilds[0].id).id)
        # 修正：View 內部沒 guild_id 建議從 interaction 拿，但這裡初始化按鈕需要狀態。
        is_on = settings.get("recommend_enabled", True)
        label_on = "🔔 整點推送：開啟" if is_on else "🔕 整點推送：關閉"
        btn_toggle = discord.ui.Button(label=label_on, style=discord.ButtonStyle.secondary)
        async def toggle_callback(interaction: discord.Interaction):
            curr = config_manager.get_guild_settings(interaction.guild.id).get("recommend_enabled", True)
            config_manager.set_guild_setting(interaction.guild.id, "recommend_enabled", not curr)
            await interaction.response.send_message(f"✅ 整點推薦系統已 {'關閉' if curr else '開啟'}！", ephemeral=True)
        btn_toggle.callback = toggle_callback
        self.add_item(btn_toggle)

        # 3. 歌手清單
        btn_artists = discord.ui.Button(label="🎤 編輯歌手清單", style=discord.ButtonStyle.primary)
        async def artist_callback(interaction: discord.Interaction):
            current = config_manager.get_guild_settings(interaction.guild.id).get("recommend_artists", [])
            class ArtistModal(discord.ui.Modal, title="編輯歌手清單"):
                inp = discord.ui.TextInput(label="請輸入歌手名稱 (以逗號分開)", default=",".join(current))
                async def on_submit(self, inter: discord.Interaction):
                    new_list = [a.strip() for a in self.inp.value.split(",") if a.strip()]
                    config_manager.set_guild_setting(inter.guild.id, "recommend_artists", new_list)
                    await inter.response.send_message(f"✅ 歌手清單已更新為：`{', '.join(new_list)}`", ephemeral=True)
            await interaction.response.send_modal(ArtistModal())
        btn_artists.callback = artist_callback
        self.add_item(btn_artists)

    def _create_modal_callback(self, label, key):
        async def callback(interaction: discord.Interaction):
            settings = config_manager.get_guild_settings(interaction.guild_id)
            await interaction.response.send_modal(StringConfigModal(label, key, settings.get(key)))
        return callback

    async def _back_to_main(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="🔧 請選擇你要修改的設定類別：", view=self.parent_view)

# --- Main Admin Panel ---

class ControlPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != 1113353915010920452:
            await interaction.response.send_message("❌ 這是高階管理面板，非擁有者禁止操作！🐾", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔧 模組開關", style=discord.ButtonStyle.primary, row=0, custom_id="admin_v2_modules")
    async def modules(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ModuleSettingsView(self.bot, self)
        await interaction.response.edit_message(content="📂 **[模組設定]** 點擊下方按鈕切換功能開關：", view=view)

    @discord.ui.button(label="🔰 安全與身分組", style=discord.ButtonStyle.primary, row=0, custom_id="admin_v2_security")
    async def security_cfg(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfigSettingsView(self.bot, self, "security")
        await interaction.response.edit_message(content="🛡️ **[安全設定]** 修改驗證與權限相關參數：", view=view)

    @discord.ui.button(label="📩 聯絡/支援設定", style=discord.ButtonStyle.primary, row=0, custom_id="admin_v2_modmail")
    async def modmail_cfg(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfigSettingsView(self.bot, self, "modmail")
        await interaction.response.edit_message(content="📩 **[聯絡設定]** 設定 Modmail 的匿名性與運作方式：", view=view)

    @discord.ui.button(label="🎵 音樂推薦設定", style=discord.ButtonStyle.primary, row=1, custom_id="admin_v2_music_rec")
    async def music_rec_cfg(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfigSettingsView(self.bot, self, "music_recommend")
        await interaction.response.edit_message(content="🎵 **[音樂推薦]** 設定每小時整點推送的歌手與頻道：", view=view)

    @discord.ui.button(label="📊 系統數據", style=discord.ButtonStyle.secondary, row=2, custom_id="admin_v2_stats")
    async def stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        process = psutil.Process(os.getpid())
        mem = process.memory_info().rss / 1024 / 1024
        cpu = psutil.cpu_percent(interval=0.1)
        
        embed = discord.Embed(title="📊 Yokaro 實時監測", color=0x3498db)
        embed.add_field(name="🌡️ CPU", value=f"{cpu}%", inline=True)
        embed.add_field(name="🧠 RAM", value=f"{mem:.1f} MB", inline=True)
        embed.add_field(name="🛰️ 延遲", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔄 重啟機器人", style=discord.ButtonStyle.danger, row=1, custom_id="admin_v2_restart")
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ 正在執行熱重啟...")
        os._exit(0)
    @discord.ui.button(label="📜 伺服器列表 & 邀請", style=discord.ButtonStyle.primary, row=0, custom_id="admin_serverlist")
    async def serverlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ 只有擁有者可以使用此功能！", ephemeral=True)
            return
        view = ServerListView(self.bot)
        embed = discord.Embed(title="🔧 Bot 所在伺服器列表", description="選擇伺服器以取得邀請或離開", color=0x00ff00)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🛡️ Role 添加", style=discord.ButtonStyle.primary, row=0, custom_id="admin_roleadd")
    async def roleadd(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Owner-only command to add roles via a UI panel."""
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ 只有擁有者可以使用此功能！", ephemeral=True)
            return
        view = RoleAddView(self.bot)
        await interaction.response.edit_message(content="選擇要操作的伺服器：", view=view)

    @discord.ui.button(label="🎙️ 動態語音頻道", style=discord.ButtonStyle.primary, row=1, custom_id="admin_dynamic_voice")
    async def dynamic_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure dynamic voice channels"""
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ 只有擁有者可以使用此功能！", ephemeral=True)
            return
        view = DynamicVoiceConfigView(self.bot)
        await interaction.response.edit_message(content="🎙️ **動態語音頻道設定**\n選擇要設定的伺服器：", view=view)

# --- Server List UI ---
class ServerListView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.selected_guild = None
        self.add_item(ServerSelect(bot))
        self.add_item(LeaveGuildButton(bot))

class ServerSelect(discord.ui.Select):
    def __init__(self, bot):
        options = [discord.SelectOption(label=g.name[:100], value=str(g.id)) for g in bot.guilds]
        super().__init__(placeholder="選擇伺服器", min_values=1, max_values=1, options=options)
        self.bot = bot
    async def callback(self, interaction: discord.Interaction):
        guild_id = int(self.values[0])
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await interaction.response.send_message("⚠️ 找不到伺服器。", ephemeral=True)
            return
        channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).create_instant_invite), None)
        if channel:
            invite = await channel.create_invite(max_uses=1, unique=True)
            await interaction.response.send_message(f"🔗 **{guild.name}** 的邀請連結：{invite.url}", ephemeral=True)
            self.view.selected_guild = guild
        else:
            await interaction.response.send_message("⚠️ 沒有可用頻道建立邀請。", ephemeral=True)

class LeaveGuildButton(discord.ui.Button):
    def __init__(self, bot):
        super().__init__(label="離開選擇的伺服器", style=discord.ButtonStyle.danger)
        self.bot = bot
    async def callback(self, interaction: discord.Interaction):
        selected_guild = getattr(self.view, "selected_guild", None)
        if not selected_guild:
            await interaction.response.send_message("⚠️ 請先選擇伺服器以取得邀請。", ephemeral=True)
            return
        try:
            await selected_guild.leave()
            await interaction.response.send_message(f"✅ 已離開伺服器 **{selected_guild.name}**。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 離開伺服器失敗：{e}", ephemeral=True)

# --- Role Add UI ---
class RoleAddView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(GuildSelect(bot))

class GuildSelect(discord.ui.Select):
    def __init__(self, bot):
        options = [discord.SelectOption(label=g.name[:100], value=str(g.id)) for g in bot.guilds]
        super().__init__(placeholder="選擇伺服器", min_values=1, max_values=1, options=options)
        self.bot = bot
    async def callback(self, interaction: discord.Interaction):
        guild_id = int(self.values[0])
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await interaction.response.send_message("⚠️ 找不到伺服器。", ephemeral=True)
            return
        view = RoleSelectView(self.bot, guild)
        await interaction.response.edit_message(content=f"已選擇 **{guild.name}**，請選擇要新增的身分組或建立新身分組。", view=view)

class RoleSelectView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild = guild
        self.add_item(RoleSelect(guild))
        self.add_item(CreateRoleButton(guild))
        # Add restore button if there are recently deleted roles
        if hasattr(bot, 'deleted_roles') and guild.id in bot.deleted_roles:
            self.add_item(RestoreRoleButton(bot, guild))

class RoleSelect(discord.ui.Select):
    def __init__(self, guild: discord.Guild):
        options = [discord.SelectOption(label=r.name, value=str(r.id)) for r in guild.roles if not r.is_default()]
        super().__init__(placeholder="選擇已有身分組", min_values=1, max_values=1, options=options)
        self.guild = guild
        self.selected_role = None
    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        role = self.guild.get_role(role_id)
        self.selected_role = role
        # Provide a button to assign the role to the invoking user
        view = AssignRoleView(self.guild, role)
        await interaction.response.send_message(
            f"✅ 已選擇身分組 **{role.name}** (ID: {role.id})。點擊下方按鈕給予您此身分組。",
            view=view,
            ephemeral=True
        )

class AssignRoleView(discord.ui.View):
    def __init__(self, guild: discord.Guild, role: discord.Role):
        super().__init__(timeout=60)
        self.guild = guild
        # Store role ID to prevent stale Role objects
        self.role_id = role.id
        self.role_name = role.name
        self.role_color = role.color
        self.role_permissions = role.permissions.value
        self.role_hoist = role.hoist
        self.role_mentionable = role.mentionable
        self.role_position = role.position

    @discord.ui.button(label="💎 給我這個身分組", style=discord.ButtonStyle.success)
    async def give_me_self(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Assign role to the invoking user (self)
        member = self.guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await self.guild.fetch_member(interaction.user.id)
            except Exception:
                await interaction.response.send_message(
                    "⚠️ 無法取得您的會員資訊，請確保您在目標伺服器中。",
                    ephemeral=True
                )
                return
        # Retrieve the role using stored role_id
        role = self.guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message("⚠️ 找不到該身分組，請稍後再試。", ephemeral=True)
            return
        try:
            await member.add_roles(role)
            await interaction.response.send_message(
                f"✅ 已將身分組 **{role.name}** 給予 <@{member.id}>。",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 給予身分組失敗：{e}", ephemeral=True)

    @discord.ui.button(label="🗑️ 移除我的身分組", style=discord.ButtonStyle.danger)
    async def remove_me_self(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Remove role from the invoking user (self)
        member = self.guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await self.guild.fetch_member(interaction.user.id)
            except Exception:
                await interaction.response.send_message(
                    "⚠️ 無法取得您的會員資訊，請確保您在目標伺服器中。",
                    ephemeral=True
                )
                return
        # Retrieve the role using stored role_id
        role = self.guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message("⚠️ 找不到該身分組，請稍後再試。", ephemeral=True)
            return
        try:
            await member.remove_roles(role)
            await interaction.response.send_message(
                f"✅ 已從 <@{member.id}> 移除身分組 **{role.name}**。",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 移除身分組失敗：{e}", ephemeral=True)

    @discord.ui.button(label="👤 給成員身分組", style=discord.ButtonStyle.primary)
    async def give_me_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Open a modal to request a member ID or mention, pass role_id instead of role object
        await interaction.response.send_modal(AssignRoleMemberModal(self.guild, self.role_id))

    @discord.ui.button(label="🔄 歸還身分組", style=discord.ButtonStyle.success)
    async def toggle_persistent_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Toggle persistent role (auto-restore on rejoin)
        member = self.guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.send_message(
                "⚠️ 無法取得您的會員資訊。",
                ephemeral=True
            )
            return
        
        # Initialize persistent roles storage if needed
        if not hasattr(interaction.client, 'persistent_roles'):
            interaction.client.persistent_roles = {}
        
        guild_id = self.guild.id
        user_id = interaction.user.id
        
        if guild_id not in interaction.client.persistent_roles:
            interaction.client.persistent_roles[guild_id] = {}
        
        # Check if user already has this role as persistent
        if user_id in interaction.client.persistent_roles[guild_id]:
            if self.role_id in interaction.client.persistent_roles[guild_id][user_id]:
                # Remove from persistent list
                interaction.client.persistent_roles[guild_id][user_id].remove(self.role_id)
                if not interaction.client.persistent_roles[guild_id][user_id]:
                    del interaction.client.persistent_roles[guild_id][user_id]
                await interaction.response.send_message(
                    f"✅ 已關閉 **{self.role_name}** 的自動歸還功能。\n退出伺服器後將不再自動獲得此身分組。",
                    ephemeral=True
                )
            else:
                # Add to persistent list
                if user_id not in interaction.client.persistent_roles[guild_id]:
                    interaction.client.persistent_roles[guild_id][user_id] = []
                interaction.client.persistent_roles[guild_id][user_id].append(self.role_id)
                await interaction.response.send_message(
                    f"✅ 已開啟 **{self.role_name}** 的自動歸還功能。\n退出伺服器後重新加入時會自動獲得此身分組。",
                    ephemeral=True
                )
        else:
            # Add to persistent list
            interaction.client.persistent_roles[guild_id][user_id] = [self.role_id]
            await interaction.response.send_message(
                f"✅ 已開啟 **{self.role_name}** 的自動歸還功能。\n退出伺服器後重新加入時會自動獲得此身分組。",
                ephemeral=True
            )

    @discord.ui.button(label="❌ 刪除身分組", style=discord.ButtonStyle.danger)
    async def delete_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Confirm deletion
        role = self.guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message("⚠️ 找不到該身分組，可能已被刪除。", ephemeral=True)
            return
        
        # Create confirmation view
        confirm_view = ConfirmDeleteView(self.guild, self.role_id, self.role_name, self.role_color, 
                                         self.role_permissions, self.role_hoist, self.role_mentionable, 
                                         self.role_position)
        await interaction.response.send_message(
            f"⚠️ **確認刪除**\n你確定要刪除身分組 **{role.name}** 嗎？\n此操作無法復原（除非使用復原功能）。",
            view=confirm_view,
            ephemeral=True
        )

class AssignRoleMemberModal(discord.ui.Modal, title="給成員身分組"):
    def __init__(self, guild: discord.Guild, role_id: int):
        super().__init__()
        self.guild = guild
        self.role_id = role_id
        self.member_input = discord.ui.TextInput(
            label="成員 ID 或 @ 提及",
            placeholder="輸入成員的 ID 或 @提及",
            required=True
        )
        self.add_item(self.member_input)

    async def on_submit(self, interaction: discord.Interaction):
        import re
        content = self.member_input.value.strip()
        match = re.search(r"(\d{17,})", content)
        if not match:
            await interaction.response.send_message("⚠️ 無效的成員 ID。", ephemeral=True)
            return
        member_id = int(match.group(1))
        
        # Fetch the member
        member = self.guild.get_member(member_id)
        if member is None:
            try:
                member = await self.guild.fetch_member(member_id)
            except Exception:
                await interaction.response.send_message(
                    "⚠️ 找不到該成員，請確保成員在目標伺服器中。",
                    ephemeral=True
                )
                return
        
        # Get the role using stored role_id
        role = self.guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message("⚠️ 找不到該身分組，請稍後再試。", ephemeral=True)
            return
        
        try:
            await member.add_roles(role)
            await interaction.response.send_message(
                f"✅ 已將身分組 **{role.name}** 給予 <@{member.id}>。",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 給予身分組失敗：{e}", ephemeral=True)



class ConfirmDeleteView(discord.ui.View):
    def __init__(self, guild: discord.Guild, role_id: int, role_name: str, role_color: int, 
                 role_permissions: int, role_hoist: bool, role_mentionable: bool, role_position: int):
        super().__init__(timeout=30)
        self.guild = guild
        self.role_id = role_id
        self.role_name = role_name
        self.role_color = role_color
        self.role_permissions = role_permissions
        self.role_hoist = role_hoist
        self.role_mentionable = role_mentionable
        self.role_position = role_position

    @discord.ui.button(label="✅ 確認刪除", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = self.guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message("⚠️ 找不到該身分組，可能已被刪除。", ephemeral=True)
            return
        
        try:
            # Save role data before deletion
            role_data = {
                'id': self.role_id,
                'name': self.role_name,
                'color': self.role_color,
                'permissions': self.role_permissions,
                'hoist': self.role_hoist,
                'mentionable': self.role_mentionable,
                'position': self.role_position,
                'deleted_at': discord.utils.utcnow().timestamp()
            }
            
            # Store in bot's deleted_roles dictionary
            if not hasattr(interaction.client, 'deleted_roles'):
                interaction.client.deleted_roles = {}
            
            if self.guild.id not in interaction.client.deleted_roles:
                interaction.client.deleted_roles[self.guild.id] = []
            
            interaction.client.deleted_roles[self.guild.id].append(role_data)
            
            # Delete the role
            role_name = role.name
            await role.delete(reason="Deleted via admin panel")
            
            await interaction.response.edit_message(
                content=f"✅ 已成功刪除身分組 **{role_name}**。\n💡 提示：使用「🔄 復原身分組」按鈕可恢復此身分組（需在30分鐘內）。",
                view=None
            )
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 刪除失敗：{e}", ephemeral=True)

    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ 已取消刪除操作。", view=None)


class RestoreRoleView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild = guild
        # In a real implementation, you would store deleted roles in a database
        # For now, we'll show a message that this feature needs a database
        self.add_item(RestoreRoleSelect(guild))


class RestoreRoleButton(discord.ui.Button):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(label="🔄 復原身分組", style=discord.ButtonStyle.primary, row=1)
        self.bot = bot
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        # Get recently deleted roles for this guild
        deleted_roles = getattr(self.bot, 'deleted_roles', {}).get(self.guild.id, [])
        
        if not deleted_roles:
            await interaction.response.send_message(
                "⚠️ 沒有可復原的身分組記錄。",
                ephemeral=True
            )
            return
        
        # Create view with restore options
        view = RestoreRoleSelectView(self.guild, deleted_roles)
        await interaction.response.send_message(
            "🔄 **選擇要復原的身分組**（最近30分鐘內刪除的）：",
            view=view,
            ephemeral=True
        )


class RestoreRoleSelectView(discord.ui.View):
    def __init__(self, guild: discord.Guild, deleted_roles: list):
        super().__init__(timeout=60)
        self.guild = guild
        self.deleted_roles = deleted_roles
        # Create select menu with deleted roles
        options = []
        for role_data in deleted_roles[:25]:  # Discord limit: 25 options max
            options.append(
                discord.SelectOption(
                    label=role_data['name'],
                    description=f"顏色: #{role_data['color']:06x} | 權限值: {role_data['permissions']}",
                    value=str(role_data['id'])
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="選擇要復原的身分組",
                options=options
            )
            select.callback = self.on_select
            self.add_item(select)
        else:
            select = discord.ui.Select(
                placeholder="沒有可復原的身分組",
                options=[discord.SelectOption(label="無", value="none")],
                disabled=True
            )
            self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        role_id = int(interaction.data['values'][0])
        
        # Find the role data
        role_data = None
        for r in self.deleted_roles:
            if r['id'] == role_id:
                role_data = r
                break
        
        if not role_data:
            await interaction.response.send_message("⚠️ 找不到該身分組資料。", ephemeral=True)
            return
        
        try:
            # Recreate the role with saved properties
            permissions = discord.Permissions(role_data['permissions'])
            new_role = await self.guild.create_role(
                name=role_data['name'],
                color=discord.Color(role_data['color']),
                permissions=permissions,
                hoist=role_data['hoist'],
                mentionable=role_data['mentionable']
            )
            
            # Try to set position (may fail if position is taken)
            try:
                await new_role.edit(position=min(role_data['position'], len(self.guild.roles) - 1))
            except:
                pass  # Position setting is optional
            
            # Remove from deleted roles list
            if hasattr(self.guild._state, '_connection') and hasattr(self.guild._state._connection, 'bot'):
                bot = self.guild._state._connection.bot
                if hasattr(bot, 'deleted_roles') and self.guild.id in bot.deleted_roles:
                    bot.deleted_roles[self.guild.id] = [
                        r for r in bot.deleted_roles[self.guild.id] if r['id'] != role_id
                    ]
            
            await interaction.response.edit_message(
                content=f"✅ 已成功復原身分組 **{new_role.name}** (ID: {new_role.id})！",
                view=None
            )
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 復原失敗：{e}", ephemeral=True)


# --- Dynamic Voice Channel UI ---
class DynamicVoiceConfigView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(DynamicVoiceGuildSelect(bot))

class DynamicVoiceGuildSelect(discord.ui.Select):
    def __init__(self, bot):
        options = [discord.SelectOption(label=g.name[:100], value=str(g.id)) for g in bot.guilds]
        super().__init__(placeholder="選擇伺服器", min_values=1, max_values=1, options=options)
        self.bot = bot
    
    async def callback(self, interaction: discord.Interaction):
        guild_id = int(self.values[0])
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await interaction.response.send_message("⚠️ 找不到伺服器。", ephemeral=True)
            return
        
        # Get current config or create new one
        config = self.bot.dynamic_voice_config.get(guild_id, {
            'category_id': None,
            'name_template': '🔊 {user} 的語音頻道',
            'create_text_channel': False
        })
        
        view = DynamicVoiceSettingsView(self.bot, guild, config)
        await interaction.response.edit_message(
            content=f"🎙️ **動態語音頻道設定** - {guild.name}\n"
                    f"請選擇要設定的選項：",
            view=view
        )

class DynamicVoiceSettingsView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, config: dict):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild = guild
        self.config = config
        self._update_buttons()
    
    def _update_buttons(self):
        self.clear_items()
        
        # Category selection button
        category_btn = discord.ui.Button(
            label=f"📁 類別: {self._get_category_name()}",
            style=discord.ButtonStyle.primary,
            row=0
        )
        category_btn.callback = self._select_category
        self.add_item(category_btn)
        
        # Trigger channel selection button
        trigger_name = "未設定"
        if self.config.get('trigger_channel_id'):
            trigger_channel = self.guild.get_channel(self.config['trigger_channel_id'])
            if trigger_channel:
                trigger_name = trigger_channel.name[:15]
        
        trigger_btn = discord.ui.Button(
            label=f"🎯 觸發頻道: {trigger_name}",
            style=discord.ButtonStyle.primary,
            row=0
        )
        trigger_btn.callback = self._select_trigger_channel
        self.add_item(trigger_btn)
        
        # Name template button
        name_btn = discord.ui.Button(
            label=f"📝 名稱樣式: {self.config.get('name_template', '🔊 {user} 的語音頻道')[:20]}...",
            style=discord.ButtonStyle.primary,
            row=1
        )
        name_btn.callback = self._set_name_template
        self.add_item(name_btn)
        
        # Text channel toggle button
        text_btn = discord.ui.Button(
            label=f"💬 聊天頻道: {'開啟' if self.config.get('create_text_channel') else '關閉'}",
            style=discord.ButtonStyle.success if self.config.get('create_text_channel') else discord.ButtonStyle.secondary,
            row=1
        )
        text_btn.callback = self._toggle_text_channel
        self.add_item(text_btn)
        
        # Save button
        save_btn = discord.ui.Button(label="💾 儲存設定", style=discord.ButtonStyle.success, row=2)
        save_btn.callback = self._save_config
        self.add_item(save_btn)
        
        # Disable button
        disable_btn = discord.ui.Button(label="❌ 關閉功能", style=discord.ButtonStyle.danger, row=2)
        disable_btn.callback = self._disable_feature
        self.add_item(disable_btn)
        
        # Back button
        back_btn = discord.ui.Button(label="⬅️ 返回", style=discord.ButtonStyle.secondary, row=2)
        back_btn.callback = self._go_back
        self.add_item(back_btn)
    
    def _get_category_name(self):
        category_id = self.config.get('category_id')
        if category_id:
            category = self.guild.get_channel(category_id)
            if category:
                return category.name
        return "未設定"
    
    async def _select_category(self, interaction: discord.Interaction):
        # Create select menu with categories
        categories = [c for c in self.guild.categories if isinstance(c, discord.CategoryChannel)]
        
        if not categories:
            await interaction.response.send_message("⚠️ 此伺服器沒有可用的類別。", ephemeral=True)
            return
        
        select = discord.ui.Select(
            placeholder="選擇語音頻道類別",
            options=[
                discord.SelectOption(label=c.name, value=str(c.id))
                for c in categories[:25]
            ]
        )
        
        async def select_callback(inter: discord.Interaction):
            self.config['category_id'] = int(inter.data['values'][0])
            self._update_buttons()
            await inter.response.edit_message(view=self)
        
        select.callback = select_callback
        self.clear_items()
        self.add_item(select)
        await interaction.response.edit_message(view=self)
    
    async def _select_trigger_channel(self, interaction: discord.Interaction):
        # Create select menu with voice channels in the selected category
        category_id = self.config.get('category_id')
        if not category_id:
            await interaction.response.send_message("⚠️ 請先選擇類別！", ephemeral=True)
            return
        
        category = self.guild.get_channel(category_id)
        if not category:
            await interaction.response.send_message("⚠️ 找不到選擇的類別。", ephemeral=True)
            return
        
        # Get voice channels in category
        voice_channels = [c for c in category.voice_channels]
        
        if not voice_channels:
            await interaction.response.send_message("⚠️ 此類別沒有語音頻道。請先建立一個語音頻道作為觸發器。", ephemeral=True)
            return
        
        select = discord.ui.Select(
            placeholder="選擇觸發語音頻道（任何人加入都會被轉移到新頻道）",
            options=[
                discord.SelectOption(label=c.name, value=str(c.id))
                for c in voice_channels[:25]
            ]
        )
        
        async def select_callback(inter: discord.Interaction):
            self.config['trigger_channel_id'] = int(inter.data['values'][0])
            self._update_buttons()
            await inter.response.edit_message(view=self)
        
        select.callback = select_callback
        self.clear_items()
        self.add_item(select)
        await interaction.response.edit_message(view=self)
    
    async def _set_name_template(self, interaction: discord.Interaction):
        modal = discord.ui.Modal(title="設定語音頻道名稱樣式")
        
        template_input = discord.ui.TextInput(
            label="名稱樣式",
            placeholder="使用 {user} 代表使用者名稱",
            default=self.config.get('name_template', '🔊 {user} 的語音頻道'),
            required=True
        )
        modal.add_item(template_input)
        
        async def on_submit(inter: discord.Interaction):
            self.config['name_template'] = template_input.value
            self._update_buttons()
            await inter.response.edit_message(view=self)
        
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
    
    async def _toggle_text_channel(self, interaction: discord.Interaction):
        self.config['create_text_channel'] = not self.config.get('create_text_channel', False)
        self._update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def _save_config(self, interaction: discord.Interaction):
        if not self.config.get('category_id'):
            await interaction.response.send_message(
                "⚠️ 請先選擇語音頻道類別！",
                ephemeral=True
            )
            return
        
        # Save config
        self.bot.dynamic_voice_config[self.guild.id] = self.config
        
        await interaction.response.send_message(
            f"✅ 已儲存動態語音頻道設定！\n"
            f"📁 類別: {self._get_category_name()}\n"
            f"📝 名稱樣式: {self.config.get('name_template')}\n"
            f"💬 聊天頻道: {'開啟' if self.config.get('create_text_channel') else '關閉'}",
            ephemeral=True
        )
    
    async def _disable_feature(self, interaction: discord.Interaction):
        if self.guild.id in self.bot.dynamic_voice_config:
            del self.bot.dynamic_voice_config[self.guild.id]
        
        await interaction.response.send_message(
            "✅ 已關閉動態語音頻道功能。",
            ephemeral=True
        )
    
    async def _go_back(self, interaction: discord.Interaction):
        view = DynamicVoiceConfigView(self.bot)
        await interaction.response.edit_message(
            content="🎙️ **動態語音頻道設定**\n選擇要設定的伺服器：",
            view=view
        )


# --- Dynamic Voice Channel Control Panel ---
class VoiceControlPanel(discord.ui.View):
    def __init__(self, bot, voice_channel_id: int, text_channel_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.voice_channel_id = voice_channel_id
        self.text_channel_id = text_channel_id
    
    def get_channels(self, guild: discord.Guild):
        voice_channel = guild.get_channel(self.voice_channel_id)
        text_channel = guild.get_channel(self.text_channel_id)
        return voice_channel, text_channel
    
    @discord.ui.button(label="🔒 鎖定頻道", style=discord.ButtonStyle.primary, row=0)
    async def lock_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_channel, text_channel = self.get_channels(interaction.guild)
        if not voice_channel:
            await interaction.response.send_message("⚠️ 語音頻道不存在。", ephemeral=True)
            return
        
        try:
            await voice_channel.set_permissions(interaction.guild.default_role, connect=False)
            if text_channel:
                await text_channel.set_permissions(interaction.guild.default_role, send_messages=False)
            await interaction.response.send_message("🔒 已鎖定頻道。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 鎖定失敗：{e}", ephemeral=True)
    
    @discord.ui.button(label="🔓 解鎖頻道", style=discord.ButtonStyle.success, row=0)
    async def unlock_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_channel, text_channel = self.get_channels(interaction.guild)
        if not voice_channel:
            await interaction.response.send_message("⚠️ 語音頻道不存在。", ephemeral=True)
            return
        
        try:
            await voice_channel.set_permissions(interaction.guild.default_role, connect=None)
            if text_channel:
                await text_channel.set_permissions(interaction.guild.default_role, send_messages=None)
            await interaction.response.send_message("🔓 已解鎖頻道。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 解鎖失敗：{e}", ephemeral=True)
    
    @discord.ui.button(label="👑 轉移所有權", style=discord.ButtonStyle.primary, row=0)
    async def transfer_ownership(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_channel, text_channel = self.get_channels(interaction.guild)
        if not voice_channel:
            await interaction.response.send_message("⚠️ 語音頻道不存在。", ephemeral=True)
            return
        
        members_in_channel = voice_channel.members
        if not members_in_channel:
            await interaction.response.send_message("⚠️ 頻道中沒有成員。", ephemeral=True)
            return
        
        select = discord.ui.Select(
            placeholder="選擇要轉移所有權的成員",
            options=[
                discord.SelectOption(label=m.display_name, value=str(m.id))
                for m in members_in_channel[:25]
            ]
        )
        
        async def select_callback(inter: discord.Interaction):
            new_owner_id = int(inter.data['values'][0])
            new_owner = interaction.guild.get_member(new_owner_id)
            
            if not new_owner:
                await inter.response.send_message("⚠️ 找不到該成員。", ephemeral=True)
                return
            
            try:
                await voice_channel.set_permissions(new_owner, manage_channels=True, move_members=True)
                if text_channel:
                    await text_channel.set_permissions(new_owner, manage_channels=True, manage_messages=True)
                await inter.response.send_message(f"👑 已將頻道所有權轉移給 {new_owner.mention}。", ephemeral=True)
            except Exception as e:
                await inter.response.send_message(f"⚠️ 轉移失敗：{e}", ephemeral=True)
        
        select.callback = select_callback
        self.clear_items()
        self.add_item(select)
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(label="⚙️ 頻道設定", style=discord.ButtonStyle.secondary, row=1)
    async def channel_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_channel, text_channel = self.get_channels(interaction.guild)
        if not voice_channel:
            await interaction.response.send_message("⚠️ 語音頻道不存在。", ephemeral=True)
            return
        
        view = ChannelSettingsView(self.bot, voice_channel, text_channel)
        embed = discord.Embed(
            title="⚙️ 頻道設定",
            description=f"語音頻道：{voice_channel.name}\n文字頻道：{text_channel.name if text_channel else '無'}",
            color=0x3498db
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="🔇 禁言所有人", style=discord.ButtonStyle.danger, row=1)
    async def mute_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_channel, _ = self.get_channels(interaction.guild)
        if not voice_channel:
            await interaction.response.send_message("⚠️ 語音頻道不存在。", ephemeral=True)
            return
        
        try:
            for member in voice_channel.members:
                await member.edit(mute=True)
            await interaction.response.send_message("🔇 已禁言所有成員。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 禁言失敗：{e}", ephemeral=True)
    
    @discord.ui.button(label="🔊 解除禁言", style=discord.ButtonStyle.success, row=1)
    async def unmute_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_channel, _ = self.get_channels(interaction.guild)
        if not voice_channel:
            await interaction.response.send_message("⚠️ 語音頻道不存在。", ephemeral=True)
            return
        
        try:
            for member in voice_channel.members:
                await member.edit(mute=False)
            await interaction.response.send_message("🔊 已解除所有成員的禁言。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 解除禁言失敗：{e}", ephemeral=True)


class ChannelSettingsView(discord.ui.View):
    def __init__(self, bot, voice_channel: discord.VoiceChannel, text_channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.bot = bot
        self.voice_channel = voice_channel
        self.text_channel = text_channel
    
    @discord.ui.button(label="📝 重新命名", style=discord.ButtonStyle.primary, row=0)
    async def rename_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = discord.ui.Modal(title="重新命名頻道")
        name_input = discord.ui.TextInput(
            label="新名稱",
            placeholder="輸入頻道名稱",
            default=self.voice_channel.name,
            required=True
        )
        modal.add_item(name_input)
        
        async def on_submit(inter: discord.Interaction):
            try:
                new_name = name_input.value
                await self.voice_channel.edit(name=new_name)
                if self.text_channel:
                    await self.text_channel.edit(name=f"語音-{new_name}")
                await inter.response.send_message(f"✅ 已重新命名為：{new_name}", ephemeral=True)
            except Exception as e:
                await inter.response.send_message(f"⚠️ 重新命名失敗：{e}", ephemeral=True)
        
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👥 限制人數", style=discord.ButtonStyle.primary, row=0)
    async def limit_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = discord.ui.Modal(title="限制成員數量")
        limit_input = discord.ui.TextInput(
            label="人數限制 (0 = 無限制)",
            placeholder="輸入數字，例如：5",
            default=str(self.voice_channel.user_limit),
            required=True
        )
        modal.add_item(limit_input)
        
        async def on_submit(inter: discord.Interaction):
            try:
                limit = int(limit_input.value)
                await self.voice_channel.edit(user_limit=limit)
                await inter.response.send_message(f"✅ 已設定人數限制為：{limit if limit > 0 else '無限制'}", ephemeral=True)
            except Exception as e:
                await inter.response.send_message(f"⚠️ 設定失敗：{e}", ephemeral=True)
        
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="❌ 關閉面板", style=discord.ButtonStyle.danger, row=1)
    async def close_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ 已關閉控制面板。", view=None)


class CreateRoleButton(discord.ui.Button):
    def __init__(self, guild: discord.Guild):
        super().__init__(label="🆕 建立新身分組", style=discord.ButtonStyle.success)
        self.guild = guild
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateRoleModal(self.guild))

class CreateRoleModal(discord.ui.Modal, title="建立新身分組"):
    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.guild = guild
        self.name_input = discord.ui.TextInput(label="身分組名稱", placeholder="輸入身分組名稱", required=True)
        self.add_item(self.name_input)
        self.admin_toggle = discord.ui.TextInput(label="是否設為管理員(su)", placeholder="yes / no", required=False)
        self.add_item(self.admin_toggle)
    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value.strip()
        admin_flag = self.admin_toggle.value.lower() in ["yes", "y", "true", "1"]
        perms = discord.Permissions(administrator=True) if admin_flag else discord.Permissions()
        try:
            role = await self.guild.create_role(name=name, permissions=perms)
            await interaction.response.send_message(f"✅ 成功建立身分組 **{role.name}** （ID: {role.id}）。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 建立身分組失敗：{e}", ephemeral=True)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(ControlPanelView(bot))
        
        # Initialize persistent_roles if not exists
        if not hasattr(bot, 'persistent_roles'):
            bot.persistent_roles = {}
        
        # Initialize dynamic voice channels config
        if not hasattr(bot, 'dynamic_voice_config'):
            bot.dynamic_voice_config = {}  # {guild_id: {category_id, name_template, create_text_channel}}
        
        # Track dynamic voice channels and their text channels
        if not hasattr(bot, 'dynamic_voice_channels'):
            bot.dynamic_voice_channels = {}  # {voice_channel_id: text_channel_id}
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Automatically restore persistent roles when a member rejoins"""
        guild_id = member.guild.id
        user_id = member.id
        
        # Check if there are persistent roles for this user
        if hasattr(self.bot, 'persistent_roles'):
            if guild_id in self.bot.persistent_roles:
                if user_id in self.bot.persistent_roles[guild_id]:
                    roles_to_add = self.bot.persistent_roles[guild_id][user_id]
                    
                    # Add each persistent role
                    added_roles = []
                    failed_roles = []
                    
                    for role_id in roles_to_add:
                        role = member.guild.get_role(role_id)
                        if role:
                            try:
                                await member.add_roles(role, reason="Persistent role auto-restore")
                                added_roles.append(role.name)
                            except Exception as e:
                                failed_roles.append(role.name)
                    
                    # Log the result
                    if added_roles:
                        print(f"✅ [持久身分組] 已自動歸還身分組給 {member.name}: {', '.join(added_roles)}")
                    if failed_roles:
                        print(f"⚠️ [持久身分組] 無法歸還以下身分組給 {member.name}: {', '.join(failed_roles)}")
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle dynamic voice channel creation and deletion"""
        if not hasattr(self.bot, 'dynamic_voice_config'):
            return
        
        guild_id = member.guild.id
        if guild_id not in self.bot.dynamic_voice_config:
            return
        
        config = self.bot.dynamic_voice_config[guild_id]
        category_id = config.get('category_id')
        trigger_channel_id = config.get('trigger_channel_id')
        name_template = config.get('name_template', '🔊 {user} 的語音頻道')
        create_text_channel = config.get('create_text_channel', False)
        
        if not trigger_channel_id:
            return
        
        # Get the category
        category = member.guild.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return
        
        # User joined the trigger channel
        if after.channel and after.channel.id == trigger_channel_id:
            # Create a new dynamic voice channel
            new_channel_name = name_template.replace('{user}', member.display_name)
            try:
                new_voice = await member.guild.create_voice_channel(
                    name=new_channel_name,
                    category=category,
                    reason="Dynamic voice channel created"
                )
                
                # Move user to new channel
                await member.move_to(new_voice)
                
                # Create text channel if enabled
                if create_text_channel:
                    text_channel = await member.guild.create_text_channel(
                        name=f"語音-{member.display_name}",
                        category=category,
                        reason="Dynamic text channel for voice"
                    )
                    
                    # Store the relationship
                    self.bot.dynamic_voice_channels[new_voice.id] = text_channel.id
                    
                    # Send welcome message with control panel
                    try:
                        embed = discord.Embed(
                            title="🎙️ 語音控制面板",
                            description="使用下方按鈕來控制你的語音頻道",
                            color=0x3498db
                        )
                        embed.add_field(
                            name="功能說明",
                            value="• 🔒/🔓 鎖定/解鎖頻道\n"
                                "• 👑 轉移所有權給其他人\n"
                                "• ⚙️ 重新命名、限制人數\n"
                                "• 🔇 禁言/解除禁言所有人",
                            inline=False
                        )
                        
                        view = VoiceControlPanel(self.bot, new_voice.id, text_channel.id)
                        await text_channel.send(embed=embed, view=view)
                    except:
                        pass
                
                print(f"✅ [動態語音] 已為 {member.display_name} 建立語音頻道: {new_channel_name}")
            except Exception as e:
                print(f"⚠️ [動態語音] 建立頻道失敗: {e}")
        
        # User left a voice channel
        if before.channel and before.channel.category_id == category_id:
            # Check if channel is now empty
            if len(before.channel.members) == 0:
                # Delete the voice channel if it's a dynamic one
                if before.channel.id in self.bot.dynamic_voice_channels:
                    text_channel_id = self.bot.dynamic_voice_channels[before.channel.id]
                    
                    # Delete text channel first
                    if text_channel_id:
                        text_channel = member.guild.get_channel(text_channel_id)
                        if text_channel:
                            try:
                                await text_channel.delete(reason="Dynamic voice channel empty")
                            except:
                                pass
                    
                    # Delete from tracking
                    del self.bot.dynamic_voice_channels[before.channel.id]
                
                # Delete the voice channel (but not the trigger channel)
                if before.channel.id != trigger_channel_id:
                    try:
                        await before.channel.delete(reason="Dynamic voice channel empty")
                        print(f"🗑️ [動態語音] 已刪除空白的語音頻道: {before.channel.name}")
                    except Exception as e:
                        print(f"⚠️ [動態語音] 刪除頻道失敗: {e}")

    @commands.hybrid_command(name='serverlist')
    async def serverlist(self, ctx):
        """Owner‑only command to display the server list UI."""
        if ctx.author.id != OWNER_ID:
            await ctx.send("❌ 只有擁有者可以使用此功能！")
            return
        view = ServerListView(self.bot)
        embed = discord.Embed(title="🔧 Bot 所在伺服器列表", description="選擇伺服器以取得邀請或離開", color=0x00ff00)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name='roleadd')
    async def roleadd(self, ctx):
        """Owner‑only command to display the role‑add UI panel."""
        if ctx.author.id != OWNER_ID:
            await ctx.send("❌ 只有擁有者可以使用此功能！")
            return
        view = RoleAddView(self.bot)
        await ctx.send("選擇要操作的伺服器：", view=view)

    @commands.hybrid_command(name='panel', aliases=['後台', '控制台'])
    async def panel(self, ctx):
        """高階管理後台 (僅限擁有者與受權管理員)"""
        mgmt = self.bot.get_cog("ManagementCog")
        if not (mgmt and mgmt.is_high_admin(ctx.author.id)):
            return await ctx.send("❌ 嘿！妳沒有進入洛洛管理後台的通行證喔！🐾")
        embed = discord.Embed(
            title="🛠️ Yokaro 高階管理後台 V2",
            description="歡迎來到全功能管理面板！請點擊下方按鈕進行細項設定。",
            color=0x2c3e50
        )
        embed.set_footer(text="提示：所有修改將即時儲存至 guild_settings.json")
        await ctx.send(embed=embed, view=ControlPanelView(self.bot))

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
