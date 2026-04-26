import discord
from discord.ext import commands
import asyncio

class VoiceAICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ducking_active = True # 預設開啟 Ducking
        self.original_volumes = {} # guild_id: vol

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # 簡單的 Ducking 邏輯：監聽成員是否開啟麥克風說話
        # 注意：這僅是狀態監聽。真正的實時音量壓低需要監聽語音封包（Packet Receiver）
        # 這裡我們實作一個基於 Discord Speaking 狀態的 Ducking
        pass

    @commands.Cog.listener()
    async def on_speaking(self, member, speaking):
        """當有人開始說話時，壓低音量"""
        if member.bot: return
        
        vc = member.guild.voice_client
        if not vc or not vc.source: return
        
        music_cog = self.bot.get_cog("MusicCog")
        if not music_cog: return
        
        state = music_cog.get_state(member.guild.id)
        
        if speaking:
            # 有人說話：壓低音量到 0.1 (10%)
            if member.guild.id not in self.original_volumes:
                self.original_volumes[member.guild.id] = vc.source.volume
            vc.source.volume = 0.1
        else:
            # 停止說話：恢復原始音量
            await asyncio.sleep(1.0) # 緩衝一秒
            if member.guild.id in self.original_volumes:
                vc.source.volume = self.original_volumes.pop(member.guild.id)

    @commands.command(name='ducking')
    async def toggle_ducking(self, ctx):
        """開關自動降音 (Ducking) 模式"""
        self.ducking_active = not self.ducking_active
        status = "開啟" if self.ducking_active else "關閉"
        await ctx.send(f"🐥 **自動降音 (Ducking) 模式已 {status}！**")

async def setup(bot):
    await bot.add_cog(VoiceAICog(bot))
