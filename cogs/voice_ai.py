import discord
from discord.ext import commands
import asyncio

class VoiceAICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ducking_active = True
        self.original_vols = {} # gid: vol

    @commands.Cog.listener()
    async def on_speaking(self, member, speaking):
        """瞬發 Ducking：有人說話音量立刻下降"""
        if member.bot or not self.ducking_active: return
        
        vc = member.guild.voice_client
        if not vc or not vc.source: return
        
        # 獲取音樂組件
        music_cog = self.bot.get_cog("MusicCog")
        if not music_cog: return
        
        state = music_cog.get_state(member.guild.id)
        
        if speaking:
            # 偵測到說話
            if member.guild.id not in self.original_vols:
                self.original_vols[member.guild.id] = vc.source.volume
            
            # 瞬降到 15% 音量
            vc.source.volume = 0.15
        else:
            # 停止說話，等待 0.8 秒回升 (避免斷斷續續)
            await asyncio.sleep(0.8)
            if member.guild.id in self.original_vols:
                vc.source.volume = self.original_vols.pop(member.guild.id)

    @commands.command(name='ducking')
    async def toggle_ducking(self, ctx):
        """開關 Ducking 自動降音模式"""
        self.ducking_active = not self.ducking_active
        status = "✅ 已開啟" if self.ducking_active else "❌ 已關閉"
        await ctx.send(f"🐥 **語音 Ducking 模式 {status}**")

    @commands.command(name='vibe')
    async def vibe_check(self, ctx):
        """根據頻道熱度自動切換濾鏡"""
        # 這裡未來可整合訊息頻率偵測
        await ctx.send("🔮 **正在感應頻道氛圍... 目前氣氛：Chill。**")

async def setup(bot):
    await bot.add_cog(VoiceAICog(bot))
