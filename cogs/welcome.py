import discord
from discord.ext import commands
import os
import json
import random
from easy_pil import Editor, load_image_async, Font, Canvas

# 隨機高品質二次元/動漫美景清單 (Anime Scenery)
RANDOM_BGS = [
    "https://images.unsplash.com/photo-1578632738980-230ca3a461bb?q=80&w=1200&h=600&fit=crop", # 數位城鎮
    "https://images.unsplash.com/photo-1541512416146-3cf58d6b27cc?q=80&w=1200&h=600&fit=crop", # 幻想森林
    "https://images.unsplash.com/photo-1605142127144-8fc19904948a?q=80&w=1200&h=600&fit=crop", # 星空神社
    "https://images.unsplash.com/photo-1528360983277-13d401cdc186?q=80&w=1200&h=600&fit=crop", # 日本街頭
    "https://images.unsplash.com/photo-1502134249126-9f3755a50d78?q=80&w=1200&h=600&fit=crop", # 宇宙銀河
    "https://images.unsplash.com/photo-1493246507139-91e8bef99c17?q=80&w=1200&h=600&fit=crop", # 夢幻山脈
    "https://images.unsplash.com/photo-1523733566440-2816999a83a5?q=80&w=1200&h=600&fit=crop"  # 城市黎明
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
                await ctx.send(f"✨ 這是為 {member.mention} 準備的【奢華二次元】歡迎預覽！嗷嗷嗷～", file=file)
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
            await ctx.send("✨ 嗷嗷嗷！已將本頻道設定為【迎新大廳】！洛洛準備好畫筆，要用二次元美景迎接新人囉！🎨")

    async def create_welcome_card(self, member):
        """極致奢華繪圖邏輯：二次元風格 + 毛玻璃質感"""
        try:
            # 1. 準備隨機背景 (寬度稍微加寬，營造氣氛)
            bg_url = random.choice(RANDOM_BGS)
            try:
                bg_image = await load_image_async(bg_url)
                background = Editor(bg_image).resize((1100, 500))
            except:
                background = Editor(Canvas((1100, 500), color="#2c3e50"))

            # 2. 製作毛玻璃矩陣 (中心透明黑色遮罩)
            overlay = Canvas((1100, 500), color=(0, 0, 0, 100)) # 全局微暗
            background.paste(Editor(overlay), (0, 0))
            
            # 中心文字背板 (毛玻璃感)
            glass_plate = Canvas((800, 300), color=(255, 255, 255, 30))
            background.paste(Editor(glass_plate), (150, 100))

            # 3. 載入中文字體
            if os.path.exists(FONT_PATH):
                font_title = Font(FONT_PATH, size=90)
                font_name = Font(FONT_PATH, size=70)
                font_sub = Font(FONT_PATH, size=40)
            else:
                font_title = Font.poppins(variant="bold", size=90)
                font_name = Font.poppins(variant="bold", size=70)
                font_sub = Font.poppins(variant="light", size=40)

            # 4. 處理頭像 (加厚圓框)
            avatar_url = member.display_avatar.url
            avatar_image = await load_image_async(str(avatar_url))
            
            profile = Editor(avatar_image).resize((220, 220)).circle_image()
            # 漸層感外框
            border = Editor(Canvas((240, 240), color="#ffffff")).circle_image()
            border.paste(profile, (10, 10))

            # 5. 組合配置 (稍微偏左的頭貼，文字排列在旁)
            background.paste(border, (200, 130))
            
            # 文字細節
            background.text((470, 140), "NEW MEMBER", font=font_sub, color="#fab1a0")
            background.text((470, 190), f"{member.name}", font=font_name, color="white")
            background.text((470, 275), f"你是第 {member.guild.member_count} 顆降落的星辰", font=font_sub, color="#dfe6e9")
            
            # 裝飾性線條
            line = Canvas((400, 5), color="#ff7675")
            background.paste(Editor(line), (470, 265))

            return discord.File(fp=background.image_bytes, filename="welcome_luxury.png")
        except Exception as e:
            print(f"奢華繪圖失敗: {e}")
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
