import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from utils.i18n import t

load_dotenv()

from discord import app_commands

XP_PER_MESSAGE = int(os.getenv("XP_PER_MESSAGE", 10))
LEVELS_FILE = "levels.json"

class LevelsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.levels = self.load_levels()

    def load_levels(self):
        if os.path.exists(LEVELS_FILE):
            with open(LEVELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_levels(self):
        with open(LEVELS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.levels, f, indent=4)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        user_id = str(message.author.id)
        if user_id not in self.levels:
            self.levels[user_id] = {"xp": 0, "level": 1}
        
        self.levels[user_id]["xp"] += XP_PER_MESSAGE
        
        # 升級計算: 每一等級需要的 XP = 等級 * 100
        current_xp = self.levels[user_id]["xp"]
        current_level = self.levels[user_id]["level"]
        next_level_xp = current_level * 200
        
        if current_xp >= next_level_xp:
            self.levels[user_id]["level"] += 1
            self.levels[user_id]["xp"] = 0
            new_level = self.levels[user_id]["level"]
            
            # 只有在伺服器頻道才發送升級訊息
            if message.guild:
                gid = message.guild.id
                await message.channel.send(
                    t(gid, "level.up", user=message.author.display_name, level=new_level)
                )
            
            # 自動贈送身分組範例 (設定等級 5 為 '高級成員')
            if message.guild and new_level == 5:
                role = discord.utils.get(message.guild.roles, name="資深成員")
                if role: await message.author.add_roles(role)
            
        self.save_levels()

    @commands.hybrid_command(name='profile', aliases=['等級'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def profile(self, ctx, user: discord.User = None):
        user = user or ctx.author
        user_id = str(user.id)
        gid = ctx.guild.id if ctx.guild else None
        
        # 獲取名稱
        display_name = getattr(user, "display_name", user.name)
        if user_id in self.levels:
            lv = self.levels[user_id]["level"]
            xp = self.levels[user_id]["xp"]
            embed = discord.Embed(title=t(gid, "level.profile.title", user=display_name), color=0xf39c12)
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(name=t(gid, "level.profile.level"), value=f"LV. {lv}", inline=True)
            embed.add_field(name=t(gid, "level.profile.xp"), value=f"{xp} / {lv * 200}", inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(t(gid, "level.no_data"))

async def setup(bot):
    await bot.add_cog(LevelsCog(bot))
