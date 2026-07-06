import discord
from discord.ext import commands
import json
import os
import aiohttp

class WidgetDataModal(discord.ui.Modal, title="編輯 Widget 資料 📝"):
    def __init__(self, cog, user_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        
        # 載入現有資料或預設值
        data = self.cog.get_user_data(user_id)
        
        self.username_input = discord.ui.TextInput(
            label="名字 (Username)",
            default=data.get("username", "培根"),
            max_length=32,
            required=True
        )
        self.hometown_input = discord.ui.TextInput(
            label="出生/家鄉 (Hometown)",
            default=data.get("hometown", "中華民國"),
            max_length=64,
            required=True
        )
        self.bio_input = discord.ui.TextInput(
            label="個人簡介 (Bio/Status)",
            default=data.get("bio", "喜歡追V 是個宅，是一個國中生~"),
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=True
        )
        self.level_input = discord.ui.TextInput(
            label="等級 (Level)",
            default=data.get("level", "100"),
            max_length=10,
            required=True
        )
        self.food_input = discord.ui.TextInput(
            label="最喜歡的食物 (Favorite Food)",
            default=data.get("food", "布丁"),
            max_length=32,
            required=True
        )
        
        self.add_item(self.username_input)
        self.add_item(self.hometown_input)
        self.add_item(self.bio_input)
        self.add_item(self.level_input)
        self.add_item(self.food_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.cog.save_user_data(self.user_id, {
            "username": self.username_input.value,
            "hometown": self.hometown_input.value,
            "bio": self.bio_input.value,
            "level": self.level_input.value,
            "food": self.food_input.value
        })
        await interaction.response.send_message("✅ 資料已成功儲存！請點選下方 **「一鍵同步到 Discord ⚡」** 送出。", ephemeral=True)

class IconSelect(discord.ui.Select):
    def __init__(self, cog, user_id):
        self.cog = cog
        self.user_id = user_id
        options = [
            discord.SelectOption(label="圖標 1 (4bb63a8378...)", value="4bb63a837823f35d66a3046fd8abadf1-removebg-preview.png", description="粉紅馬卡龍可愛培根"),
            discord.SelectOption(label="圖標 2 (9dda3ed533...)", value="9dda3ed5332c0626d263fb471014a94e-removebg-preview.png", description="元氣動漫風頭像"),
            discord.SelectOption(label="圖標 3 (images__6_...)", value="images__6_-removebg-preview.png", description="經典風格配圖"),
            discord.SelectOption(label="圖標 4 (images__7_...)", value="images__7_-removebg-preview.png", description="超酷炫二次元圖標"),
            discord.SelectOption(label="圖標 5 (images__8_...)", value="images__8_-removebg-preview.png", description="特別設計風格頭像"),
        ]
        super().__init__(placeholder="選擇你的 Widget 大頭貼圖標...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.cog.save_user_icon(self.user_id, self.values[0])
        await interaction.response.send_message(f"✅ 圖標已設定為：`{self.values[0]}`！請點選下方 **「一鍵同步到 Discord ⚡」**。", ephemeral=True)

class IconSelectView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=60)
        self.add_item(IconSelect(cog, user_id))

class WidgetControlView(discord.ui.View):
    def __init__(self, cog, user_id, oauth_url):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        
        # 1. 授權連結按鈕
        self.add_item(discord.ui.Button(
            label="1. 授權 Widget 連結 🔗",
            style=discord.ButtonStyle.link,
            url=oauth_url
        ))

    @discord.ui.button(label="2. 編輯 Widget 資料 📝", style=discord.ButtonStyle.primary, row=1)
    async def edit_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ 您不是發起此指令的玩家！", ephemeral=True)
        modal = WidgetDataModal(self.cog, self.user_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="3. 選擇圖標 🖼️", style=discord.ButtonStyle.secondary, row=1)
    async def select_icon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ 您不是發起此指令的玩家！", ephemeral=True)
        view = IconSelectView(self.cog, self.user_id)
        await interaction.response.send_message("👇 請在下方下拉選單中選擇你的 Widget 大頭貼圖示：", view=view, ephemeral=True)

    @discord.ui.button(label="4. 一鍵同步到 Discord ⚡", style=discord.ButtonStyle.success, row=2)
    async def sync_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ 您不是發起此指令的玩家！", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        data = self.cog.get_user_data(self.user_id)
        icon = self.cog.get_user_icon(self.user_id)
        
        status, response_text = await self.cog.sync_widget(self.user_id, data, icon)
        
        if status == 200:
            embed = discord.Embed(
                title="⚡ Widget 同步成功！",
                description="您的個人檔案 Widget 資訊已經更新成功！",
                color=0x2ecc71
            )
            embed.add_field(name="用戶", value=data.get("username", "培根"))
            embed.add_field(name="等級", value=f"雜魚等級 {data.get('level', '100')}")
            embed.add_field(name="出生地", value=data.get("hometown", "中華民國"))
            embed.add_field(name="最愛食物", value=data.get("food", "布丁"))
            embed.add_field(name="簡介", value=data.get("bio", "喜歡追V 是個宅"), inline=False)
            if icon:
                embed.set_thumbnail(url=self.cog.get_image_url(icon))
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                f"❌ 同步失敗 (HTTP {status})！\n"
                f"**可能原因**：\n"
                f"1. 您可能尚未點擊按鈕 1 授權（或登入錯誤）。\n"
                f"2. 伺服器與 Discord API 連線逾時。\n\n"
                f"詳細錯誤訊息：`{response_text}`",
                ephemeral=True
            )

class WidgetCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "widget_users.json"
        self.user_db = self.load_db()

    def load_db(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def save_db(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.user_db, f, indent=4, ensure_ascii=False)

    def get_user_data(self, user_id):
        user_key = str(user_id)
        if user_key not in self.user_db:
            self.user_db[user_key] = {}
        return self.user_db[user_key].get("data", {
            "username": "培根",
            "hometown": "中華民國",
            "bio": "喜歡追V 是個宅，是一個國中生~",
            "level": "100",
            "food": "布丁"
        })

    def get_user_icon(self, user_id):
        user_key = str(user_id)
        if user_key not in self.user_db:
            return "4bb63a837823f35d66a3046fd8abadf1-removebg-preview.png"
        return self.user_db[user_key].get("icon", "4bb63a837823f35d66a3046fd8abadf1-removebg-preview.png")

    def save_user_data(self, user_id, data):
        user_key = str(user_id)
        if user_key not in self.user_db:
            self.user_db[user_key] = {}
        self.user_db[user_key]["data"] = data
        self.save_db()

    def save_user_icon(self, user_id, icon_filename):
        user_key = str(user_id)
        if user_key not in self.user_db:
            self.user_db[user_key] = {}
        self.user_db[user_key]["icon"] = icon_filename
        self.save_db()

    def get_user_token(self, user_id):
        user_key = str(user_id)
        if user_key not in self.user_db:
            return None
        return self.user_db[user_key].get("access_token")


    def get_image_url(self, filename):
        domain = os.getenv("CUSTOM_DOMAIN")
        if domain:
            return f"https://{domain}/image/{filename}"
        # 尋找 WebPanelCog 獲取 Cloudflare Tunnel URL
        webpanel = self.bot.get_cog('WebPanelCog')
        if webpanel and webpanel.tunnel_url:
            return f"{webpanel.tunnel_url}/image/{filename}"
        return f"http://localhost:8848/image/{filename}"

    async def sync_widget(self, user_id, data, icon_filename):
        # 獲取本機器人的 Application ID，解密 token 首段
        app_id = self.bot.application_id
        if not app_id:
            try:
                # 嘗試從 Token 首段 base64 還原 App ID
                import base64
                token = self.bot.http.token
                first_part = token.split(".")[0]
                # 補齊 base64 填補字元 =
                first_part += "=" * ((4 - len(first_part) % 4) % 4)
                app_id = int(base64.b64decode(first_part).decode("utf-8"))
            except:
                app_id = 1465175036938948732  # 預設 Fallback

        url = f"https://discord.com/api/v9/applications/{app_id}/users/{user_id}/identities/0/profile"
        icon_url = self.get_image_url(icon_filename) if icon_filename else ""
        
        level_val = data.get("level", "100")
        try:
            level_int = int(level_val)
        except ValueError:
            level_int = 100

        payload = {
            "username": data.get("username", "培根"),
            "data": {
                "dynamic": [
                    {"type": 1, "name": "bento", "value": data.get("hometown", "中華民國")},
                    {"type": 1, "name": "hometown", "value": data.get("hometown", "中華民國")},
                    {"type": 1, "name": "location", "value": data.get("hometown", "中華民國")},
                    {"type": 1, "name": "country", "value": data.get("hometown", "中華民國")},
                    {"type": 1, "name": "level", "value": str(level_val)},
                    {"type": 2, "name": "level", "value": level_int},
                    {"type": 1, "name": "rank", "value": f"雜魚等級{level_val}"},
                    {"type": 1, "name": "status", "value": data.get("bio", "喜歡追V 是個宅")},
                    {"type": 1, "name": "bio", "value": data.get("bio", "喜歡追V 是個宅")},
                    {"type": 1, "name": "about", "value": data.get("bio", "喜歡追V 是個宅")},
                    {"type": 1, "name": "description", "value": data.get("bio", "喜歡追V 是個宅")},
                    {"type": 1, "name": "food", "value": data.get("food", "布丁")},
                    {"type": 1, "name": "favorite_food", "value": data.get("food", "布丁")},
                    {"type": 1, "name": "pudding", "value": data.get("food", "布丁")},
                    {"type": 1, "name": "hobby", "value": "喜歡追V 是個宅"},
                ]
            }
        }
        
        if icon_url:
            payload["data"]["dynamic"].append({"type": 3, "name": "icon", "value": {"url": icon_url}})
            payload["data"]["dynamic"].append({"type": 3, "name": "avatar", "value": {"url": icon_url}})
            payload["data"]["dynamic"].append({"type": 3, "name": "image", "value": {"url": icon_url}})
            payload["data"]["dynamic"].append({"type": 3, "name": "bacon_icon", "value": {"url": icon_url}})

        # 1. 嘗試使用 User Bearer Token (推薦，直接使用 OAuth2 授權範圍)
        access_token = self.get_user_token(user_id)
        if access_token:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "DiscordBot (https://github.com/discord/discord-api-docs, 1.0.0)"
            }
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, json=payload, headers=headers) as resp:
                    status = resp.status
                    text = await resp.text()
                    if status == 200:
                        return status, text
                    print(f"⚠️ Bearer Token 同步失敗 ({status})，改用 Bot Token 備援。錯誤: {text}")

        # 2. 備援：使用 Bot Token
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bot {self.bot.http.token}",
            "User-Agent": "DiscordBot (https://github.com/discord/discord-api-docs, 1.0.0)"
        }
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, json=payload, headers=headers) as resp:
                return resp.status, await resp.text()

    @commands.command(name='widget', aliases=['bacon_widget', '小工具'])
    async def widget_cmd(self, ctx):
        """開啟培根專屬的 Widget 控制面板"""
        app_id = self.bot.application_id
        if not app_id:
            try:
                import base64
                token = self.bot.http.token
                first_part = token.split(".")[0]
                first_part += "=" * ((4 - len(first_part) % 4) % 4)
                app_id = int(base64.b64decode(first_part).decode("utf-8"))
            except:
                app_id = 1465175036938948732

        # 獲取 Bot 的網頁後台 Base URL 以傳遞給 Worker state 參數
        domain = os.getenv("CUSTOM_DOMAIN")
        if domain:
            base_url = f"https://{domain}"
        else:
            webpanel = self.bot.get_cog('WebPanelCog')
            if webpanel and webpanel.tunnel_url:
                base_url = webpanel.tunnel_url
            else:
                base_url = "http://localhost:8848"

        import urllib.parse
        state_encoded = urllib.parse.quote(base_url)

        # 組合 OAuth2 授權網址，以 %20 區隔 scope，並攜帶 state
        oauth_url = f"https://discord.com/oauth2/authorize?client_id={app_id}&redirect_uri=https%3A%2F%2Fyokaro520.colacat878787.workers.dev&response_type=token&scope=openid%20sdk.social_layer&state={state_encoded}"
        
        embed = discord.Embed(
            title="🥓 培根的 Widget v2 控制中樞",
            description="本介面可協助您將您的個人特徵（國中生、喜歡追V、愛吃布丁、來自中華民國）一鍵同步至 Discord 個人檔案 Widget！",
            color=0xff7f50
        )
        embed.add_field(
            name="💡 步驟說明",
            value="1. 點選下方 **「1. 授權 Widget 連結 🔗」** 完成應用程式授權。\n"
                  "2. 點選 **「2. 編輯 Widget 資料 📝」** 可輸入您的名字、簡介、等級與食物等特徵。\n"
                  "3. 點選 **「3. 選擇圖標 🖼️」** 來選擇您上傳至 `image` 資料夾的五張培根大頭貼之一。\n"
                  "4. 最後點選 **「4. 一鍵同步到 Discord ⚡」**，資料就會立刻同步至您的 Widget！",
            inline=False
        )
        embed.set_footer(text="優卡洛 ⚙️ Widget v2 助手")
        
        view = WidgetControlView(self, ctx.author.id, oauth_url)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(WidgetCog(bot))
