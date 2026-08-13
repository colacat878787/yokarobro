import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.i18n import t

class HugCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='抱抱', aliases=['hug', '擁抱'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def hug(self, ctx, target: discord.Member = None):
        """伸出可愛的小爪爪抱抱你或其他人"""
        gid = ctx.guild.id if ctx.guild else None
        if target is None:
            target = ctx.author

        anim_key = f"hug.anim.{random.randint(1, 8)}"
        animation = t(gid, anim_key)

        embed = discord.Embed(
            title=t(gid, "hug.title"),
            description=f"{ctx.author.mention} {animation}",
            color=0xffb6c1
        )

        if target != ctx.author:
            embed.add_field(
                name=t(gid, "hug.target"),
                value=t(gid, "hug.received", mention=target.mention),
                inline=False
            )

        embed.set_footer(text=t(gid, "hug.footer"))
        await ctx.send(embed=embed)

        if random.random() < 0.3:  # 30% 機率
            try:
                await ctx.message.add_reaction("💕")
            except:
                pass

async def setup(bot):
    await bot.add_cog(HugCog(bot))