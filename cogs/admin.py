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
        try:
            await member.add_roles(self.role)
            await interaction.response.send_message(
                f"✅ 已將身分組 **{self.role.name}** 給予 <@{member.id}>。",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 給予身分組失敗：{e}", ephemeral=True)

    @discord.ui.button(label="👤 給成員身分組", style=discord.ButtonStyle.primary)
    async def give_me_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Open a modal to request a member ID or mention
        await interaction.response.send_modal(AssignRoleMemberModal(self.guild, self.role))

class AssignRoleMemberModal(discord.ui.Modal, title="給成員身分組"):
    def __init__(self, guild: discord.Guild, role: discord.Role):
        super().__init__()
        self.guild = guild
        self.role = role
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
        member = self.guild.get_member(member_id)
        if member is None:
            try:
                member = await self.guild.fetch_member(member_id)
            except Exception:
                await interaction.response.send_message("⚠️ 找不到此成員於目標伺服器。", ephemeral=True)
                return
        try:
            await member.add_roles(self.role)
            await interaction.response.send_message(
                f"✅ 已將身分組 **{self.role.name}** 給予 <@{member.id}>。",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 給予身分組失敗：{e}", ephemeral=True)

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
