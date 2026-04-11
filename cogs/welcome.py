import discord
from discord.ext import commands
import os
import json
from easy_pil import Editor, load_image_async, Font, Canvas

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

    @commands.command(name='set_welcome', aliases=['歡迎', '設定歡迎'])
    @commands.has_permissions(administrator=True)
    async def set_welcome(self, ctx):
        """將當前頻道設定/取消為歡迎頻道"""
        if ctx.channel.id in self.welcome_channels:
            self.welcome_channels.remove(ctx.channel.id)
            self.save_welcome_channels()
            await ctx.send("🛑 已經取消本頻道的迎新功能惹～")
        else:
            self.welcome_channels.add(ctx.channel.id)
            self.save_welcome_channels()
            await ctx.send("✨ 嗷嗷嗷！已將本頻道設定為【迎新大廳】！有新人進來洛洛會在這裡畫圖歡迎他們喔！\n(準備好畫筆了✒️)")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        for channel_id in self.welcome_channels:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    # 1. 產生畫布與字體
                    try:
                        # 嘗試從網路抓取一張美麗的星空背景圖並稍微模糊
                        bg_image = await load_image_async("https://images.unsplash.com/photo-1542401886-65d6c61db217?q=80&w=1024&h=300&fit=crop")
                        background = Editor(bg_image).blur(amount=1)
                    except:
                        # 如果網路不穩抓不到背圖，退回素色時尚深色底
                        background = Editor(Canvas((1024, 300), color="#1e1e24"))
                        
                    poppins_big = Font.poppins(variant="bold", size=70)
                    poppins_small = Font.poppins(variant="regular", size=40)
                    poppins_light = Font.poppins(variant="light", size=30)

                    # 2. 獲取用戶大頭貼並處理成圓形
                    avatar_url = member.display_avatar.url if member.display_avatar else member.default_avatar.url
                    avatar_image = await load_image_async(str(avatar_url))
                    
                    # 替頭貼加一個白色的外框
                    profile_border = Editor(Canvas((220, 220), color="#ffffff")).circle_image()
                    profile = Editor(avatar_image).resize((200, 200)).circle_image()
                    
                    profile_border.paste(profile, (10, 10))

                    # 3. 把頭貼與邊框貼到左邊
                    background.paste(profile_border, (50, 40))

                    # 4. 畫上美美的文字文字
                    background.text((310, 80), "WELCOME", font=poppins_big, color="#ffb8b8")
                    background.text((310, 160), f"{member.name}", font=poppins_small, color="white")
                    background.text((310, 220), f"You are the {member.guild.member_count}th member!", font=poppins_light, color="#dcdde1")

                    # 5. 轉換成 Discord 圖片檔案並送出
                    file = discord.File(fp=background.image_bytes, filename="welcome_card.png")
                    await channel.send(f"歡迎 <@{member.id}> (第 {member.guild.member_count} 位星辰) 加入 **{member.guild.name}**！嗷嗷嗷～🎉", file=file)
                except Exception as e:
                    print(f"歡迎圖片繪製失敗: {e}")
                    # 如果畫圖大失敗了，至少會跳出文字歡迎
                    await channel.send(f"歡迎 <@{member.id}> 加入！(嗷嗷嗷...洛洛的畫筆突然壞掉了...)")

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
