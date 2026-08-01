import discord
from discord.ext import commands
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_dir = "backups"
        os.makedirs(self.backup_dir, exist_ok=True)
    
    @commands.command(name='備份', aliases=['backup'])
    @commands.has_permissions(administrator=True)
    async def backup_server(self, ctx):
        """備份整個伺服器的結構（身分組、頻道、權限）"""
        guild = ctx.guild
        
        # 顯示備份中訊息
        status_msg = await ctx.send("🔄 正在備份伺服器結構...")
        
        try:
            # 建立備份資料
            backup_data = {
                "backup_id": str(uuid.uuid4())[:8],
                "server_name": guild.name,
                "server_id": guild.id,
                "created_at": datetime.now().isoformat(),
                "roles": [],
                "channels": [],
                "categories": []
            }
            
            # 備份身分組（排除 @everyone）
            for role in sorted(guild.roles, reverse=True):
                if role.name != "@everyone":
                    role_data = {
                        "name": role.name,
                        "color": str(role.color),
                        "permissions": role.permissions.value,
                        "position": role.position,
                        "mentionable": role.mentionable,
                        "hoist": role.hoist,
                        "managed": role.managed
                    }
                    backup_data["roles"].append(role_data)
            
            # 備份類別和頻道
            for category in guild.categories:
                cat_data = {
                    "name": category.name,
                    "position": category.position,
                    "channels": []
                }
                
                # 備份類別下的頻道
                for channel in category.channels:
                    channel_data = await self._get_channel_data(channel)
                    cat_data["channels"].append(channel_data)
                
                backup_data["categories"].append(cat_data)
            
            # 備份沒有類別的頻道
            for channel in guild.channels:
                if not channel.category:
                    channel_data = await self._get_channel_data(channel)
                    backup_data["channels"].append(channel_data)
            
            # 儲存備份
            backup_file = os.path.join(self.backup_dir, f"{backup_data['backup_id']}.json")
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            # 建立嵌入訊息
            embed = discord.Embed(
                title="✅ 備份完成",
                description=f"伺服器結構已成功備份！",
                color=0x2ed573,
                timestamp=datetime.now()
            )
            embed.add_field(name="備份代碼", value=f"`{backup_data['backup_id']}`", inline=False)
            embed.add_field(name="伺服器名稱", value=guild.name, inline=True)
            embed.add_field(name="伺服器 ID", value=str(guild.id), inline=True)
            embed.add_field(name="身分組數量", value=str(len(backup_data["roles"])), inline=True)
            embed.add_field(name="頻道數量", value=str(sum(len(cat["channels"]) for cat in backup_data["categories"]) + len(backup_data["channels"])), inline=True)
            embed.add_field(name="備份時間", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            embed.set_footer(text="請妥善保存備份代碼，用於還原伺服器")
            
            await status_msg.edit(content=None, embed=embed)
            
        except Exception as e:
            await status_msg.edit(content=f"❌ 備份失敗：{str(e)}")
    
    @commands.command(name='還原', aliases=['restore'])
    @commands.has_permissions(administrator=True)
    async def restore_server(self, ctx, backup_id: str):
        """還原伺服器結構（使用備份代碼）"""
        # 檢查備份檔案是否存在
        backup_file = os.path.join(self.backup_dir, f"{backup_id}.json")
        if not os.path.exists(backup_file):
            return await ctx.send(f"❌ 找不到備份代碼：`{backup_id}`")
        
        try:
            # 載入備份資料
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # 建立確認嵌入訊息
            embed = discord.Embed(
                title="⚠️ 確認還原",
                description=f"你即將還原伺服器結構到以下備份：",
                color=0xffa500
            )
            embed.add_field(name="備份代碼", value=f"`{backup_data['backup_id']}`", inline=False)
            embed.add_field(name="原始伺服器", value=backup_data["server_name"], inline=True)
            embed.add_field(name="備份時間", value=datetime.fromisoformat(backup_data["created_at"]).strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            embed.add_field(name="還原內容", value=f"• {len(backup_data['roles'])} 個身分組\n• {sum(len(cat['channels']) for cat in backup_data['categories']) + len(backup_data['channels'])} 個頻道", inline=False)
            embed.add_field(name="⚠️ 注意", value="請選擇還原方式：\n🔴 **覆蓋模式**：刪除現有結構後還原\n🟢 **新增模式**：保留現有結構，只新增缺少的項目", inline=False)
            
            # 建立按鈕
            view = RestoreView(backup_data, ctx.author)
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            await ctx.send(f"❌ 讀取備份失敗：{str(e)}")
    
    @commands.command(name='備份列表', aliases=['backup_list'])
    @commands.has_permissions(administrator=True)
    async def list_backups(self, ctx):
        """列出所有可用的備份"""
        if not os.path.exists(self.backup_dir):
            return await ctx.send("📭 目前沒有任何備份")
        
        backups = []
        for filename in os.listdir(self.backup_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.backup_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        backups.append(data)
                except:
                    continue
        
        if not backups:
            return await ctx.send("📭 目前沒有任何備份")
        
        # 建立備份列表
        embed = discord.Embed(
            title="📋 備份列表",
            description=f"共找到 {len(backups)} 個備份",
            color=0x3498db
        )
        
        for backup in sorted(backups, key=lambda x: x["created_at"], reverse=True)[:10]:
            created = datetime.fromisoformat(backup["created_at"]).strftime("%Y-%m-%d %H:%M")
            channel_count = sum(len(cat["channels"]) for cat in backup["categories"]) + len(backup["channels"])
            embed.add_field(
                name=f"`{backup['backup_id']}` - {backup['server_name']}",
                value=f"時間：{created}\n身分組：{len(backup['roles'])} | 頻道：{channel_count}",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    async def _get_channel_data(self, channel) -> Dict:
        """取得頻道的資料"""
        channel_data = {
            "name": channel.name,
            "type": str(channel.type),
            "position": channel.position
        }
        
        # 文字頻道權限
        if isinstance(channel, discord.TextChannel):
            overwrites = {}
            for target, overwrite in channel.overwrites.items():
                if isinstance(target, discord.Role):
                    allow, deny = overwrite.pair()
                    overwrites[str(target.id)] = {
                        "role_name": target.name,
                        "allow": allow.value if allow else 0,
                        "deny": deny.value if deny else 0
                    }
            channel_data["permission_overwrites"] = overwrites
            channel_data["topic"] = channel.topic or ""
            channel_data["nsfw"] = channel.nsfw
        
        # 語音頻道權限
        elif isinstance(channel, discord.VoiceChannel):
            overwrites = {}
            for target, overwrite in channel.overwrites.items():
                if isinstance(target, discord.Role):
                    allow, deny = overwrite.pair()
                    overwrites[str(target.id)] = {
                        "role_name": target.name,
                        "allow": allow.value if allow else 0,
                        "deny": deny.value if deny else 0
                    }
            channel_data["permission_overwrites"] = overwrites
            channel_data["bitrate"] = channel.bitrate
            channel_data["user_limit"] = channel.user_limit
        
        return channel_data


class RestoreView(discord.ui.View):
    """還原確認按鈕"""
    
    def __init__(self, backup_data: Dict, author: discord.Member):
        super().__init__(timeout=300)
        self.backup_data = backup_data
        self.author = author
    
    @discord.ui.button(label="🔴 覆蓋模式", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def overwrite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ 只有發起者可以使用此按鈕", ephemeral=True)
        
        await interaction.response.defer()
        await self._restore_server(interaction, overwrite=True)
        self.stop()
    
    @discord.ui.button(label="🟢 新增模式", style=discord.ButtonStyle.success, emoji="✅")
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ 只有發起者可以使用此按鈕", ephemeral=True)
        
        await interaction.response.defer()
        await self._restore_server(interaction, overwrite=False)
        self.stop()
    
    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ 只有發起者可以使用此按鈕", ephemeral=True)
        
        await interaction.response.edit_message(content="❌ 已取消還原", embed=None, view=None)
        self.stop()
    
    async def _restore_server(self, interaction: discord.Interaction, overwrite: bool):
        """執行還原"""
        guild = interaction.guild
        command_channel = interaction.channel  # 記錄指令頻道，避免被刪除
        
        # 發送一個新的狀態訊息到頻道
        status_msg = await interaction.channel.send("🔄 正在還原伺服器結構...")
        
        try:
            # 如果選擇覆蓋模式，刪除現有頻道（保留指令頻道和預設頻道）
            if overwrite:
                await status_msg.edit(content="🗑️ 正在刪除現有頻道...")
                for channel in guild.channels:
                    # 保留指令頻道，避免無法發送訊息
                    if channel.id == command_channel.id:
                        continue
                    try:
                        await channel.delete()
                    except:
                        continue
            
            # 還原身分組
            await status_msg.edit(content="👥 正在還原身分組...")
            existing_roles = {role.name: role for role in guild.roles if role.name != "@everyone"}
            
            for role_data in self.backup_data["roles"]:
                # 檢查是否已存在相同名稱的身分組
                if role_data["name"] in existing_roles and not overwrite:
                    continue
                
                # 如果已存在且要覆蓋，先刪除
                if role_data["name"] in existing_roles and overwrite:
                    try:
                        await existing_roles[role_data["name"]].delete()
                    except:
                        continue
                
                # 建立新身分組
                try:
                    role = await guild.create_role(
                        name=role_data["name"],
                        color=discord.Color(int(role_data["color"])),
                        permissions=discord.Permissions(role_data["permissions"]),
                        mentionable=role_data["mentionable"],
                        hoist=role_data["hoist"]
                    )
                except Exception as e:
                    print(f"建立身分組失敗 {role_data['name']}: {e}")
            
            # 還原類別和頻道
            await status_msg.edit(content="📁 正在還原頻道...")
            
            # 建立類別對應表
            role_map = {role.name: role for role in guild.roles}
            
            for cat_data in self.backup_data["categories"]:
                try:
                    # 建立類別
                    category = await guild.create_category(cat_data["name"])
                    
                    # 建立頻道
                    for channel_data in cat_data["channels"]:
                        await self._create_channel(guild, channel_data, category, role_map)
                
                except Exception as e:
                    print(f"建立類別失敗 {cat_data['name']}: {e}")
            
            # 建立沒有類別的頻道
            for channel_data in self.backup_data["channels"]:
                try:
                    await self._create_channel(guild, channel_data, None, role_map)
                except Exception as e:
                    print(f"建立頻道失敗 {channel_data['name']}: {e}")
            
            # 完成
            embed = discord.Embed(
                title="✅ 還原完成",
                description=f"伺服器結構已成功還原！",
                color=0x2ed573,
                timestamp=datetime.now()
            )
            embed.add_field(name="還原模式", value="🔴 覆蓋模式" if overwrite else "🟢 新增模式", inline=True)
            embed.add_field(name="身分組數量", value=str(len(self.backup_data["roles"])), inline=True)
            embed.add_field(name="頻道數量", value=str(sum(len(cat["channels"]) for cat in self.backup_data["categories"]) + len(self.backup_data["channels"])), inline=True)
            
            await status_msg.edit(content=None, embed=embed)
            
        except Exception as e:
            await status_msg.edit(content=f"❌ 還原失敗：{str(e)}")
    
    async def _create_channel(self, guild: discord.Guild, channel_data: Dict, category: Optional[discord.CategoryChannel], role_map: Dict[str, discord.Role]):
        """建立頻道並設定權限"""
        try:
            # 建立頻道
            if channel_data["type"] == "text":
                channel = await guild.create_text_channel(
                    name=channel_data["name"],
                    category=category
                )
                
                # 設定權限覆蓋
                if "permission_overwrites" in channel_data:
                    for role_id, perm_data in channel_data["permission_overwrites"].items():
                        role = role_map.get(perm_data["role_name"])
                        if role:
                            await channel.set_permissions(
                                role,
                                allow=discord.Permissions(perm_data["allow"]),
                                deny=discord.Permissions(perm_data["deny"])
                            )
                
                # 設定其他屬性
                if channel_data.get("topic"):
                    await channel.edit(topic=channel_data["topic"])
                if "nsfw" in channel_data:
                    await channel.edit(nsfw=channel_data["nsfw"])
            
            elif channel_data["type"] == "voice":
                channel = await guild.create_voice_channel(
                    name=channel_data["name"],
                    category=category
                )
                
                # 設定權限覆蓋
                if "permission_overwrites" in channel_data:
                    for role_id, perm_data in channel_data["permission_overwrites"].items():
                        role = role_map.get(perm_data["role_name"])
                        if role:
                            await channel.set_permissions(
                                role,
                                allow=discord.Permissions(perm_data["allow"]),
                                deny=discord.Permissions(perm_data["deny"])
                            )
                
                # 設定其他屬性
                if "bitrate" in channel_data:
                    await channel.edit(bitrate=channel_data["bitrate"])
                if "user_limit" in channel_data:
                    await channel.edit(user_limit=channel_data["user_limit"])
        
        except Exception as e:
            print(f"建立頻道失敗 {channel_data['name']}: {e}")


async def setup(bot):
    await bot.add_cog(BackupCog(bot))