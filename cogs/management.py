import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime

BLACKLIST_FILE = "blacklist.json"
KNOWN_USERS_FILE = "known_users.json"

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
        # 存檔一次確保數據乾淨
        self._save_data(BLACKLIST_FILE, self.blacklist)

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
        return user_id in self.blacklist

    def log_user(self, user):
        uid = str(user.id)
        self.known_users[uid] = {
            "name": str(user),
            "display_name": user.display_name,
            "last_seen": datetime.datetime.now().isoformat()
        }
        self._save_data(KNOWN_USERS_FILE, self.known_users)

    @commands.group(name="manage", aliases=["監管"], invoke_without_command=True)
    async def manage_root(self, ctx):
        """監管系統主指令 (僅限擁有者)"""
        if ctx.author.id != 1113353915010920452:
            return await ctx.send("❌ 嘿！只有洛洛的親爸爸（擁有者）才能使用這個指令喔！")
        await ctx.send("❓ 請輸入子指令：`serverlist`, `userlist`, `blacklist`, `whitelist`")

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
