"""Fix 2: context_menus.py - context menus must be module-level"""
import os
os.chdir(r'D:\win11\桌點\程式作品\\yokaro')

fpath = r'cogs\context_menus.py'

full_new = '''import discord
from discord.ext import commands
from discord import app_commands
import random

# 鼓掌的鼓勵語
cheer_messages = [
    "要繼續加油哦!!",
    "做得太好了！",
    "太厲害了！",
    "繼續保持哦！",
    "你是最棒的！",
    "不可思議的表現！",
    "令人欽佩！",
    "太優秀了！"
]


# ===== 移植功能 (Context Menu - module-level required by discord.py) =====
@app_commands.context_menu(name="移植")
async def transplant_context_menu(interaction: discord.Interaction, message: discord.Message):
    """將訊息內容複製到當前頻道（移植功能)"""
    if not interaction.user.guild_permissions.manage_messages and str(interaction.user.id) != "1113353915010920452":
        await interaction.response.send_message("❌ 你沒有權限使用這個功能！", ephemeral=True)
        return

    if not message.content and not message.embeds:
        await interaction.response.send_message("❌ 這條訊息沒有內容可以移植！", ephemeral=True)
        return

    embed = discord.Embed(
        title="📋 訊息移植",
        description=message.content or "*（此訊息只有附件或 embed）*",
        color=0x3498db,
        timestamp=message.created_at
    )
    embed.set_author(
        name=f"{message.author.display_name} ({message.author})",
        icon_url=message.author.display_avatar.url
    )
    embed.add_field(
        name="🔗 原始訊息",
        value=f"[點擊查看]({message.jump_url})",
        inline=False
    )
    if message.embeds:
        embed.add_field(
            name="⚠️ 注意",
            value="原文包含 embed 內容，請查看原始訊息",
            inline=False
        )
    embed.set_footer(text=f" transplanted by {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await interaction.followup.send("✅ 訊息已移植！", ephemeral=True)


# ===== 鼓掌功能 (Context Menu) =====
@app_commands.context_menu(name="鼓掌")
async def clap_context_menu(interaction: discord.Interaction, message: discord.Message):
    """給訊息作者鼓掌鼓勵"""
    if message.author == interaction.user:
        await interaction.response.send_message("❌ 你不能給自己鼓掌哦！", ephemeral=True)
        return
    if message.author.bot:
        await interaction.response.send_message("❌ 不能給機器人鼓掌！", ephemeral=True)
        return

    cheer = random.choice(cheer_messages)
    embed = discord.Embed(
        title="👏 鼓掌時間！",
        description=f"{interaction.user.mention} 給 {message.author.mention} 鼓掌！",
        color=0xf1c40f
    )
    embed.add_field(name="💪 鼓勵語", value=cheer, inline=False)
    embed.add_field(name="📝 被鼓掌的訊息", value=f"[點擊查看]({message.jump_url})", inline=False)
    embed.set_thumbnail(url=message.author.display_avatar.url)
    embed.set_footer(text=f"鼓掌者：{interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)
    try:
        await message.add_reaction("👏")
    except:
        pass


# ===== 引用功能 (Context Menu) =====
@app_commands.context_menu(name="引用")
async def quote_context_menu(interaction: discord.Interaction, message: discord.Message):
    """將訊息轉換為引用格式"""
    embed = discord.Embed(
        title="💬 引用訊息",
        description=message.content or "*（此訊息只有附件或 embed）*",
        color=0x95a5a6,
        timestamp=message.created_at
    )
    embed.set_author(
        name=f"{message.author.display_name} ({message.author})",
        icon_url=message.author.display_avatar.url
    )
    embed.add_field(name="📌 引用自", value=f"[原始訊息]({message.jump_url})", inline=False)
    if message.embeds:
        embed.add_field(name="⚠️ 注意", value="原文包含 embed 內容", inline=False)
    embed.set_footer(text=f"引用者：{interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)


class ContextMenusCog(commands.Cog):
    """右鍵互動功能 (Context Menu)"""
    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(ContextMenusCog(bot))
    bot.tree.add_command(transplant_context_menu)
    bot.tree.add_command(clap_context_menu)
    bot.tree.add_command(quote_context_menu)
'''

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(full_new)
print('✅ context_menus.py: fixed context menus to module-level')
