import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta

class TimedRoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 儲存限時身分組資料
        # {user_id: {guild_id: [{"role_id": role_id, "expires_at": datetime}]}}
        self.timed_roles = {}
    
    @commands.hybrid_command(name='限時身分組', aliases=['timerole', '限時角色'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def timerole(self, ctx, target: discord.Member, role: discord.Role, duration: str):
        """給予用戶限時身分組
        
        使用方式：
        !限時身分組 @用戶 @身分組 1h    - 給予 1 小時
        !限時身分組 @用戶 @身分組 30m   - 給予 30 分鐘
        !限時身分組 @用戶 @身分組 1d    - 給予 1 天
        !限時身分組 @用戶 @身分組 7d    - 給予 7 天
        
        範例：
        !限時身分組 @user @VIP 24h
        /限時身分組 target:@user role:@VIP duration:12h
        """
        # 檢查權限
        if not ctx.author.guild_permissions.manage_roles and str(ctx.author.id) != "1113353915010920452":
            await ctx.send("❌ 你沒有權限使用這個指令！需要「管理身分組」權限。", ephemeral=True)
            return
        
        # 檢查 bot 的權限
        if not ctx.guild.me.top_role > role:
            await ctx.send("❌ 我的身分組等級不夠，無法給予這個身分組！", ephemeral=True)
            return
        
        # 解析時間
        duration_seconds = self._parse_duration(duration)
        if duration_seconds is None:
            await ctx.send("❌ 時間格式錯誤！請使用：1h（小時）、30m（分鐘）、1d（天）", ephemeral=True)
            return
        
        # 計算過期時間
        expires_at = datetime.now() + timedelta(seconds=duration_seconds)
        
        # 給予身分組
        try:
            await target.add_roles(role, reason=f"限時身分組 - 給予者: {ctx.author}")
        except Exception as e:
            await ctx.send(f"❌ 給予身分組失敗：{e}", ephemeral=True)
            return
        
        # 記錄限時身分組
        user_id = str(target.id)
        guild_id = str(ctx.guild.id)
        
        if user_id not in self.timed_roles:
            self.timed_roles[user_id] = {}
        
        if guild_id not in self.timed_roles[user_id]:
            self.timed_roles[user_id][guild_id] = []
        
        self.timed_roles[user_id][guild_id].append({
            "role_id": role.id,
            "expires_at": expires_at,
            "channel_id": ctx.channel.id
        })
        
        # 格式化時間顯示
        duration_str = self._format_duration(duration_seconds)
        
        # 發送確認訊息
        embed = discord.Embed(
            title="⏰ 限時身分組已授予",
            description=f"已給予 {target.mention} {role.mention} 身分組",
            color=0x2ecc71
        )
        embed.add_field(name="⏱️ 持续时间", value=duration_str, inline=True)
        embed.add_field(name="🕐 過期時間", value=f"<t:{int(expires_at.timestamp())}:F>", inline=True)
        embed.add_field(name="👤 給予者", value=ctx.author.mention, inline=True)
        embed.set_footer(text="⏳ 時間到後會自動移除身分組")
        
        await ctx.send(embed=embed)
        
        # 設定背景任務移除身分組
        self.bot.loop.create_task(self._remove_role_after(target, role, expires_at, user_id, guild_id))
    
    def _parse_duration(self, duration: str) -> int:
        """解析時間字串，返回秒數"""
        duration = duration.lower().strip()
        
        if duration.endswith('m'):
            try:
                return int(duration[:-1]) * 60
            except:
                return None
        elif duration.endswith('h'):
            try:
                return int(duration[:-1]) * 3600
            except:
                return None
        elif duration.endswith('d'):
            try:
                return int(duration[:-1]) * 86400
            except:
                return None
        else:
            return None
    
    def _format_duration(self, seconds: int) -> str:
        """格式化時間顯示"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        days = hours // 24
        
        parts = []
        if days > 0:
            parts.append(f"{days} 天")
        if hours % 24 > 0:
            parts.append(f"{hours % 24} 小時")
        if minutes > 0:
            parts.append(f"{minutes} 分鐘")
        
        return " ".join(parts) if parts else "0 分鐘"
    
    async def _remove_role_after(self, member: discord.Member, role: discord.Role, expires_at: datetime, user_id: str, guild_id: str):
        """在指定時間後移除身分組"""
        # 計算需要等待的時間
        wait_seconds = (expires_at - datetime.now()).total_seconds()
        
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        
        # 檢查身分組是否還在
        if role in member.roles:
            try:
                await member.remove_roles(role, reason="限時身分組已過期")
                
                # 發送通知
                try:
                    embed = discord.Embed(
                        title="⏰ 限時身分組已過期",
                        description=f"{member.mention} 的 {role.mention} 身分組已自動移除",
                        color=0xe74c3c
                    )
                    embed.set_footer(text="限時身分組系統")
                    
                    # 嘗試發送通知到原頻道
                    guild = self.bot.get_guild(int(guild_id))
                    if guild:
                        channel = guild.get_channel(self.timed_roles.get(user_id, {}).get(guild_id, [{}])[0].get("channel_id", 0))
                        if channel:
                            await channel.send(embed=embed)
                except:
                    pass
                
            except Exception as e:
                print(f"❌ 移除限時身分組失敗: {e}")
        
        # 從記錄中移除
        try:
            if user_id in self.timed_roles and guild_id in self.timed_roles[user_id]:
                self.timed_roles[user_id][guild_id] = [
                    r for r in self.timed_roles[user_id][guild_id]
                    if r["role_id"] != role.id
                ]
        except:
            pass
    
    @commands.hybrid_command(name='查看限時身分組', aliases=['checktimerole', '查看限時角色'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def check_timed_roles(self, ctx, target: discord.Member = None):
        """查看自己或其他人的限時身分組
        
        使用方式：
        !查看限時身分組        - 查看自己的
        !查看限時身分組 @用戶  - 查看別人的
        """
        if target is None:
            target = ctx.author
        
        user_id = str(target.id)
        guild_id = str(ctx.guild.id)
        
        # 檢查是否有記錄
        if user_id not in self.timed_roles or guild_id not in self.timed_roles[user_id]:
            await ctx.send(f"📋 {target.mention} 目前沒有限時身分組", ephemeral=True)
            return
        
        timed_list = self.timed_roles[user_id][guild_id]
        
        if not timed_list:
            await ctx.send(f"📋 {target.mention} 目前沒有限時身分組", ephemeral=True)
            return
        
        # 建立 embed
        embed = discord.Embed(
            title=f"⏰ {target.display_name} 的限時身分組",
            color=0x3498db
        )
        
        now = datetime.now()
        for i, data in enumerate(timed_list, 1):
            role = ctx.guild.get_role(data["role_id"])
            if role:
                expires_at = data["expires_at"]
                remaining = expires_at - now
                
                if remaining.total_seconds() > 0:
                    status = f"✅ 有效\n⏱️ 剩餘：{self._format_duration(int(remaining.total_seconds()))}\n🕐 過期：<t:{int(expires_at.timestamp())}:R>"
                else:
                    status = f"❌ 已過期（將自動移除）"
                
                embed.add_field(
                    name=f"{i}. {role.name}",
                    value=status,
                    inline=False
                )
        
        embed.set_footer(text=f"查詢者：{ctx.author.display_name}")
        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(TimedRoleCog(bot))