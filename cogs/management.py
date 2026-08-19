import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
from discord.ext import tasks

BLACKLIST_FILE = "blacklist.json"
KNOWN_USERS_FILE = "known_users.json"
ADMINS_FILE = "admins.json"
QUARANTINE_FILE = "quarantine_data.json"
QUARANTINE_ROLE_NAME = "小黑屋"

class ServerListView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog

    @discord.ui.button(label="🚪 讓洛洛退出伺服器", style=discord.ButtonStyle.danger)
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        class LeaveModal(discord.ui.Modal, title="🚪 執行撤退指令"):
            num = discord.ui.TextInput(label="請輸入列表中的編號 (如: 1)", placeholder="編號...", min_length=1, max_length=2)
            async def on_submit(self, inter: discord.Interaction):
                try:
                    idx = int(self.num.value) - 1
                    guilds = self.cog.last_guild_list
                    if 0 <= idx < len(guilds):
                        target = guilds[idx]
                        await inter.response.send_message(f"🚨 洛洛正在執行撤退... 即將離開 **{target.name}** (`{target.id}`)！", ephemeral=True)
                        await target.leave()
                    else:
                        await inter.response.send_message("❌ 編號超出範圍囉！", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"❌ 發生錯誤：{e}", ephemeral=True)
        
        await interaction.response.send_modal(LeaveModal(self.cog))

class ManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        raw_bl = self._load_data(BLACKLIST_FILE, [])
        self.blacklist = self._purify_blacklist(raw_bl)
        self.known_users = self._load_data(KNOWN_USERS_FILE, {})
        self.high_admins = self._load_data(ADMINS_FILE, [])
        self.quarantines = self._load_data(QUARANTINE_FILE, {})
        # 存檔一次確保數據乾淨
        self._save_data(BLACKLIST_FILE, self.blacklist)
        self._save_data(ADMINS_FILE, self.high_admins)
        self.quarantine_expiry_loop.start()

    def cog_unload(self):
        self.quarantine_expiry_loop.cancel()

    def _purify_blacklist(self, raw_list):
        import re
        purified = []
        for item in raw_list:
            # 提取純數字 ID (防止文字或標記殘留)
            match = re.search(r'\d+', str(item))
            if match:
                purified.append(match.group())
        return list(set(purified)) # 去重

    def _load_data(self, path, default):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    def _save_data(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def is_blacklisted(self, user_id):
        return str(user_id) in self.blacklist

    def is_high_admin(self, user_id):
        """檢查是否為高階管理員或擁有者"""
        uid = str(user_id)
        # 擁有者永遠是最高權限
        if uid == "1113353915010920452": 
            return True
        return uid in self.high_admins

    def log_user(self, user):
        uid = str(user.id)
        self.known_users[uid] = {
            "name": str(user),
            "display_name": user.display_name,
            "last_seen": datetime.datetime.now().isoformat()
        }
        self._save_data(KNOWN_USERS_FILE, self.known_users)

    async def _get_quarantine_role(self, guild):
        role = discord.utils.get(guild.roles, name=QUARANTINE_ROLE_NAME)
        if role is None:
            role = await guild.create_role(name=QUARANTINE_ROLE_NAME, reason="小黑屋系統")
        return role

    async def _apply_quarantine_permissions(self, guild, role):
        for channel in guild.channels:
            try:
                await channel.set_permissions(
                    role,
                    view_channel=False,
                    send_messages=False,
                    connect=False,
                    speak=False,
                    reason="小黑屋限制",
                )
            except (discord.Forbidden, discord.HTTPException):
                continue

    async def _release_quarantine(self, guild_id, user_id, notify_channel_id=None):
        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return
        record = self.quarantines.get(str(guild_id), {}).pop(str(user_id), None)
        if not record:
            return
        member = guild.get_member(int(user_id))
        role = guild.get_role(int(record["role_id"]))
        if member and role and role in member.roles:
            try:
                await member.remove_roles(role, reason="小黑屋時間到期")
            except (discord.Forbidden, discord.HTTPException):
                pass
        self._save_data(QUARANTINE_FILE, self.quarantines)
        if notify_channel_id:
            channel = guild.get_channel(int(notify_channel_id))
            if channel and member:
                try:
                    await channel.send(f"✅ {member.mention} 的小黑屋時間已到，已恢復頻道權限。")
                except (discord.Forbidden, discord.HTTPException):
                    pass

    @tasks.loop(seconds=30)
    async def quarantine_expiry_loop(self):
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        for guild_id, users in list(self.quarantines.items()):
            for user_id, record in list(users.items()):
                if record.get("expires_at", 0) <= now:
                    await self._release_quarantine(guild_id, user_id)

    @quarantine_expiry_loop.before_loop
    async def before_quarantine_expiry_loop(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="小黑屋", aliases=["quarantine", "禁閉"])
    @commands.has_permissions(manage_roles=True)
    async def quarantine(self, ctx, target: discord.Member, duration: str):
        """將成員暫時限制在小黑屋，例如 !小黑屋 @使用者 1h。"""
        bot_member = ctx.guild.me
        if not bot_member.guild_permissions.manage_roles or not bot_member.guild_permissions.manage_channels:
            await ctx.send("❌ 我需要「管理身分組」和「管理頻道」權限才能使用小黑屋。", ephemeral=True)
            return
        if target.guild_permissions.administrator:
            await ctx.send("❌ 管理員權限可以繞過頻道隱藏，無法套用小黑屋。", ephemeral=True)
            return
        if target == ctx.guild.owner or target.top_role >= ctx.author.top_role:
            await ctx.send("❌ 你不能把同等或更高身分組的成員關進小黑屋。", ephemeral=True)
            return
        seconds = self._parse_quarantine_duration(duration)
        if seconds is None or seconds <= 0:
            await ctx.send("❌ 時間格式錯誤！請使用 `30m`、`1h` 或 `1d`。", ephemeral=True)
            return
        if ctx.guild.me.top_role <= target.top_role:
            await ctx.send("❌ 我的身分組等級不夠，無法限制這位成員。", ephemeral=True)
            return

        role = await self._get_quarantine_role(ctx.guild)
        await self._apply_quarantine_permissions(ctx.guild, role)
        try:
            await target.add_roles(role, reason=f"小黑屋 {duration}，執行者：{ctx.author}")
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send("❌ 加入小黑屋失敗，請確認我有管理身分組權限。", ephemeral=True)
            return

        guild_data = self.quarantines.setdefault(str(ctx.guild.id), {})
        guild_data[str(target.id)] = {
            "role_id": role.id,
            "expires_at": datetime.datetime.now(datetime.timezone.utc).timestamp() + seconds,
            "channel_id": ctx.channel.id,
        }
        self._save_data(QUARANTINE_FILE, self.quarantines)
        await ctx.send(f"🚫 {target.mention} 已進入小黑屋，將於 <t:{int(guild_data[str(target.id)]['expires_at'])}:R> 恢復。")

    def _parse_quarantine_duration(self, value):
        import re
        match = re.fullmatch(r"(\d+)\s*([mhd])", value.strip().lower())
        if not match:
            return None
        return int(match.group(1)) * {"m": 60, "h": 3600, "d": 86400}[match.group(2)]

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        guild_data = self.quarantines.get(str(channel.guild.id), {})
        if not guild_data:
            return
        role_id = next(iter(guild_data.values())).get("role_id")
        role = channel.guild.get_role(int(role_id)) if role_id else None
        if role:
            try:
                await channel.set_permissions(role, view_channel=False, send_messages=False, connect=False, speak=False, reason="小黑屋限制")
            except (discord.Forbidden, discord.HTTPException):
                pass

    @commands.group(name="manage", aliases=["監管"], invoke_without_command=True)
    async def manage_root(self, ctx):
        """監管系統主指令 (僅限擁有者)"""
        if ctx.author.id != 1113353915010920452:
            return await ctx.send("❌ 嘿！只有洛洛的親爸爸（擁有者）才能使用這個指令喔！")
        await ctx.send("❓ 請輸入子指令：`serverlist`, `userlist`, `blacklist`, `whitelist`, `admin`")

    @manage_root.group(name="admin", invoke_without_command=True)
    async def admin_group(self, ctx):
        """高階管理員管理 (僅限擁有者)"""
        if ctx.author.id != 1113353915010920452: return
        await ctx.send("❓ 請選擇：`admin set @人` 或 `admin remove @人`")

    @admin_group.command(name="set")
    async def admin_set(self, ctx, user: discord.User):
        """任命高階管理員 (公開宣示)"""
        if ctx.author.id != 1113353915010920452: return
        uid = str(user.id)
        if uid in self.high_admins:
            return await ctx.send(f"⚠️ **{user}** 已經是高階管理員囉！")
        
        self.high_admins.append(uid)
        self._save_data(ADMINS_FILE, self.high_admins)
        
        await ctx.send(f"🎊 **【洛洛重要公告】** 🎊\n\n感謝親爸爸的信任！恭喜 {user.mention} 正式受封為 **高階管理員**！\n從現在起，妳也擁有了進入洛洛機密後台的權限喔！嗷嗷嗷～✨")

    @admin_group.command(name="remove")
    async def admin_remove(self, ctx, user: discord.User):
        """撤銷高階管理員權限"""
        if ctx.author.id != 1113353915010920452: return
        uid = str(user.id)
        if uid not in self.high_admins:
            return await ctx.send(f"❓ **{user}** 原本就不是高階管理員。")
        
        self.high_admins.remove(uid)
        self._save_data(ADMINS_FILE, self.high_admins)
        await ctx.send(f"✅ 已成功卸除 **{user}** 的高階管理員職務。")

    @manage_root.command(name="serverlist", aliases=["伺服器清單", "sl"])
    async def server_list(self, ctx):
        if ctx.author.id != 1113353915010920452: return
        """列出機器人加入的所有伺服器 (附帶退出按鈕)"""
        guilds = sorted(self.bot.guilds, key=lambda g: g.member_count, reverse=True)
        self.last_guild_list = guilds # 暫存清單供退出使用
        count = len(guilds)
        
        desc = f"📊 目前洛洛所在的伺服器數量：**{count}**\n\n"
        for i, g in enumerate(guilds[:25], 1): # 限制顯示前 25 個
            desc += f"**[{i}]** **{g.name}** (`{g.id}`) - 👥 {g.member_count} 人\n"
        
        if count > 25:
            desc += f"\n*...以及其他 {count-25} 個伺服器*"

        embed = discord.Embed(title="🌐 洛洛伺服器清單", description=desc, color=0x3498db)
        embed.set_footer(text="點擊下方按鈕並輸入編號，可讓洛洛退出該伺服器")
        
        view = ServerListView(self)
        await ctx.send(embed=embed, view=view)

    @manage_root.command(name="userlist", aliases=["用戶清單", "ul"])
    async def user_list(self, ctx):
        if ctx.author.id != 1113353915010920452: return
        """列出曾經使用過洛洛指令的用戶 (自動追蹤)"""
        count = len(self.known_users)
        if count == 0:
            return await ctx.send("🌚 目前還沒有捕獲到任何活躍用戶資料。")

        desc = f"👤 目前已追蹤到的活躍用戶：**{count}** 位\n\n"
        sorted_users = sorted(self.known_users.items(), key=lambda x: x[1].get('last_seen', ''), reverse=True)
        
        for uid, info in sorted_users[:20]:
            desc += f"• **{info['display_name']}** (`{uid}`) - 🕒 {info['last_seen'][:16]}\n"

        embed = discord.Embed(title="👥 洛洛活躍用戶名冊", description=desc, color=0x2ecc71)
        embed.set_footer(text="僅顯示最近活躍的前 20 名")
        await ctx.send(embed=embed)

    @manage_root.command(name="blacklist", aliases=["黑名單", "bl"])
    async def blacklist_user(self, ctx, user: discord.User, *, reason="違反使用規範"):
        if ctx.author.id != 1113353915010920452: return
        """將用戶加入黑名單並私訊通知"""
        user_id = str(user.id)
        if user_id in self.blacklist:
            return await ctx.send(f"⚠️ **{user}** 已經在黑名單中囉！")
        
        self.blacklist.append(user_id)
        self._save_data(BLACKLIST_FILE, self.blacklist)
        
        notification_status = "✅ 已成功發送私訊通知"
        try:
            embed = discord.Embed(title="🚫 洛洛服務狀態通知", color=0xff0000)
            embed.description = f"您的使用權限已被管理員暫停。\n**原因：** {reason}\n\n如有疑問請聯絡開發者。"
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            await user.send(embed=embed)
        except Exception as e:
            notification_status = f"⚠️ 私訊發送失敗 (用戶可能關閉 DM)：{e}"

        await ctx.send(f"🚫 已將用戶 **{user}** (`{user_id}`) 加入黑名單。\n{notification_status}")

    @manage_root.command(name="whitelist", aliases=["白名單", "wl"])
    async def whitelist_user(self, ctx, user: discord.User):
        if ctx.author.id != 1113353915010920452: return
        """從黑名單移除用戶"""
        user_id = str(user.id)
        if user_id not in self.blacklist:
            return await ctx.send(f"❓ **{user}** 本來就不在黑名單中。")
        
        self.blacklist.remove(user_id)
        self._save_data(BLACKLIST_FILE, self.blacklist)
        await ctx.send(f"✅ 已將用戶 **{user}** (`{user_id}`) 從黑名單移除，恢復服務使用權。")

async def setup(bot):
    await bot.add_cog(ManagementCog(bot))
