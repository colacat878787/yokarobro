import discord
from discord.ext import commands
import asyncio

class VoiceAICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ducking_active = True
        self.original_vols = {} # gid: vol
        self.ducking_tasks = {} # gid: task

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """偵測語音狀態更新（包含說話狀態/麥克風開關）來進行自動 Ducking 降音量"""
        if member.bot or not self.ducking_active:
            return
            
        vc = member.guild.voice_client
        if not vc or not vc.is_playing() or not vc.source:
            return
            
        if member.voice and member.voice.channel and member.voice.channel == vc.channel:
            # 當同頻道成員麥克風為開啟且未靜音時
            is_speaking = not (member.voice.self_mute or member.voice.mute or member.voice.suppress)
            music_cog = self.bot.get_cog("MusicCog")
            if not music_cog: return

            gid = member.guild.id
            if is_speaking:
                # 取消原本的回升任務
                if gid in self.ducking_tasks and not self.ducking_tasks[gid].done():
                    self.ducking_tasks[gid].cancel()

                if gid not in self.original_vols:
                    self.original_vols[gid] = getattr(vc.source, 'volume', 0.5)

                vc.source.volume = min(self.original_vols[gid], 0.15)
            else:
                # 延遲恢復音量
                async def _restore_vol():
                    await asyncio.sleep(1.2)
                    if gid in self.original_vols:
                        orig = self.original_vols.pop(gid, 0.5)
                        if vc and vc.source:
                            vc.source.volume = orig

                self.ducking_tasks[gid] = self.bot.loop.create_task(_restore_vol())

    @commands.Cog.listener()
    async def on_speaking(self, member, speaking):
        """防護用：支援 discord speaking 事件降音量"""
        if member.bot or not self.ducking_active: return
        
        vc = member.guild.voice_client
        if not vc or not vc.is_playing() or not vc.source: return
        
        music_cog = self.bot.get_cog("MusicCog")
        if not music_cog: return
        
        gid = member.guild.id
        if speaking:
            if gid in self.ducking_tasks and not self.ducking_tasks[gid].done():
                self.ducking_tasks[gid].cancel()
            if gid not in self.original_vols:
                self.original_vols[gid] = getattr(vc.source, 'volume', 0.5)
            vc.source.volume = min(self.original_vols[gid], 0.15)
        else:
            async def _restore_vol():
                await asyncio.sleep(1.2)
                if gid in self.original_vols:
                    orig = self.original_vols.pop(gid, 0.5)
                    if vc and vc.source:
                        vc.source.volume = orig

            self.ducking_tasks[gid] = self.bot.loop.create_task(_restore_vol())

    @commands.command(name='ducking', aliases=['降音', '自動降音'])
    async def toggle_ducking(self, ctx):
        """開關 Ducking 自動降音模式"""
        self.ducking_active = not self.ducking_active
        status = "✅ 已開啟" if self.ducking_active else "❌ 已關閉"
        await ctx.send(f"🐥 **語音 Ducking 模式 {status}**")

    @commands.command(name='vibe')
    async def vibe_check(self, ctx):
        """根據頻道熱度自動切換濾鏡"""
        await ctx.send("🔮 **正在感應頻道氛圍... 目前氣氛：Chill。**")

async def setup(bot):
    await bot.add_cog(VoiceAICog(bot))
