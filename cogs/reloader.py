import discord
from discord.ext import commands
import asyncio, sys

class ReloadCog(commands.Cog):
    """Provides a command to reload all cogs and reinstall requirements."""
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='reloadcog', aliases=['reload'])
    async def reloadcog(self, ctx: discord.Interaction):
        """Reload every loaded extension and run pip install -r requirements.txt.
        Usage: `!reloadcog`
        """
        await ctx.send('🔄 正在重新載入所有模組並安裝依賴套件，請稍候...')
        # Reload extensions
        reloaded = []
        for ext in list(self.bot.extensions.keys()):
            try:
                await self.bot.unload_extension(ext)
                await self.bot.load_extension(ext)
                reloaded.append(ext)
            except Exception as e:
                await ctx.send(f'⚠️ 重新載入 {ext} 失敗: {e}')
        # Reinstall requirements
        proc = await asyncio.create_subprocess_shell(
            f"{sys.executable} -m pip install -r requirements.txt",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            await ctx.send('✅ 依賴套件重新安裝完成。')
        else:
            await ctx.send(f'❌ 依賴安裝失敗:\n```\n{stderr.decode()}\n```')
        await ctx.send(f'✅ 已重新載入模組: {"、".join(reloaded)}')

async def setup(bot):
    await bot.add_cog(ReloadCog(bot))
