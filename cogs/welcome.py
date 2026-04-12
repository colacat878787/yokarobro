import discord
from discord.ext import commands
import os
import json
import random
from easy_pil import Editor, load_image_async, Font, Canvas

# 隨機背景清單 (Unsplash 高畫質風景/星空)
RANDOM_BGS = [
    "https://images.unsplash.com/photo-1534796636912-3b95b3ab5986?q=80&w=1024&h=400&fit=crop", # 星空
    "https://images.unsplash.com/photo-1506744038136-46273834b3fb?q=80&w=1024&h=400&fit=crop", # 山水
    "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?q=80&w=1024&h=400&fit=crop", # 雪山
    "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?q=80&w=1024&h=400&fit=crop", # 森林
    "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?q=80&w=1024&h=400&fit=crop", # 綠意
    "https://images.unsplash.com/photo-1501785888041-af3ef285b470?q=80&w=1024&h=400&fit=crop"  # 湖泊
]

FONT_PATH = "assets/fonts/NotoSansTC-Bold.otf"

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_channels = set()
        self.load_welcome_channels()

    def load_welcome_channels(self):
        if os.path.exists('welcome_channels.json'):
            try:
                with open('welcome_channels.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.welcome_channels = set(data)
            except Exception as e:
                print(f"無法讀取歡迎頻道設定: {e}")

    def save_welcome_channels(self):
        try:
            with open('welcome_channels.json', 'w', encoding='utf-8') as f:
                json.dump(list(self.welcome_channels), f)
        except Exception as e:
            print(f"無法儲存歡迎頻道設定: {e}")

    @commands.group(name='welcome', aliases=['歡迎'], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def welcome_group(self, ctx, member: discord.Member = None):
        """(管理員) 預覽歡迎圖片：!welcome @用戶"""
        if member is None:
            await ctx.send("❓ 請標記一位成員來測試歡迎圖片喔！例如：`!welcome @用戶`")
            return
        
        async with ctx.typing():
            file = await self.create_welcome_card(member)
            if file:
                await ctx.send(f"✨ 這是為 {member.mention} 準備的歡迎預覽！嗷嗷嗷～", file=file)
            else:
                await ctx.send("❌ 哎呀，繪製圖片時發生意外了！")

    @welcome_group.command(name='set')
    @commands.has_permissions(administrator=True)
    async def set_welcome(self, ctx):
        """(管理員) 將當前頻道設定/取消為歡迎頻道"""
        if ctx.channel.id in self.welcome_channels:
            self.welcome_channels.remove(ctx.channel.id)
            self.save_welcome_channels()
            await ctx.send("🛑 已經取消本頻道的迎新功能惹～")
        else:
            self.welcome_channels.add(ctx.channel.id)
            self.save_welcome_channels()
            await ctx.send("✨ 嗷嗷嗷！已將本頻道設定為【迎新大廳】！有新人進來洛洛會在這裡畫圖歡迎他們喔！")

    async def create_welcome_card(self, member):
        """核心繪圖邏輯：支援中文字體與隨機背景"""
        try:
            # 1. 準備隨機背景
            bg_url = random.choice(RANDOM_BGS)
            try:
                bg_image = await load_image_async(bg_url)
                background = Editor(bg_image).resize((1024, 400)).blur(amount=1)
            except:
                background = Editor(Canvas((1024, 400), color="#1e1e24"))

            # 2. 載入中文字體 (若字體檔不存在則退回預設)
            if os.path.exists(FONT_PATH):
                font_big = Font(FONT_PATH, size=80)
                font_name = Font(FONT_PATH, size=60)
                font_small = Font(FONT_PATH, size=35)
            else:
                font_big = Font.poppins(variant="bold", size=80)
                font_name = Font.poppins(variant="bold", size=60)
                font_small = Font.poppins(variant="light", size=35)

            # 3. 處理頭像
            avatar_url = member.display_avatar.url
            avatar_image = await load_image_async(str(avatar_url))
            
            # 製作帶有發光感的外框
            profile_outer = Editor(Canvas((260, 260), color="#ffffff")).circle_image()
            profile = Editor(avatar_image).resize((240, 240)).circle_image()
            profile_outer.paste(profile, (10, 10))

            # 4. 組合圖片
            background.paste(profile_outer, (60, 70))
            
            # 繪製文字 (加上陰影效果感)
            background.text((360, 90), "WELCOME", font=font_big, color="#ff7675")
            background.text((360, 185), f"{member.name}", font=font_name, color="white")
            background.text((360, 265), f"歡迎來到 {member.guild.name}", font=font_small, color="#fab1a0")
            background.text((360, 310), f"你是第 {member.guild.member_count} 位星辰成員喔！嗷嗷嗷～", font=font_small, color="#dfe6e9")

            return discord.File(fp=background.image_bytes, filename="welcome.png")
        except Exception as e:
            print(f"繪圖發生錯誤: {e}")
            return None

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not self.welcome_channels:
            return
            
        file = await self.create_welcome_card(member)
        
        for channel_id in self.welcome_channels:
            channel = self.bot.get_channel(channel_id)
            if channel:
                if file:
                    await channel.send(f"🌌 歡迎新星 <@{member.id}> 墜入 **{member.guild.name}**！", file=file)
                else:
                    await channel.send(f"🌌 歡迎新星 <@{member.id}> 墜入 **{member.guild.name}**！(洛洛今天畫圖手感不太好，只能文字歡迎你惹...嗷嗚)")

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
