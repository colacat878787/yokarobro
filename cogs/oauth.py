import discord
from discord.ext import commands
from discord import app_commands
import os
import secrets
import json
import requests
from datetime import datetime
from flask import render_template_string, request, jsonify, redirect
import urllib.parse

# OAuth HTML 模板
OAUTH_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>加入伺服器 - Yokaro</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        h1 {
            color: #333;
            margin-bottom: 20px;
            font-size: 2rem;
        }
        p {
            color: #666;
            margin-bottom: 30px;
            line-height: 1.6;
        }
        .btn {
            display: inline-block;
            background: #5865F2;
            color: white;
            padding: 15px 40px;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 600;
            font-size: 1.1rem;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
        }
        .btn:hover {
            background: #4752C4;
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(88, 101, 242, 0.4);
        }
        .error {
            background: #fee;
            color: #c33;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .success {
            background: #efe;
            color: #3c3;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        {% if error %}
        <div class="error">
            <h2>❌ 發生錯誤</h2>
            <p>{{ error }}</p>
        </div>
        {% endif %}
        
        {% if success %}
        <div class="success">
            <h2>✅ 成功！</h2>
            <p>{{ success }}</p>
        </div>
        {% endif %}
        
        {% if not success %}
        <h1>🎉 加入伺服器</h1>
        <p>點擊下方按鈕，透過 Discord OAuth2 授權即可快速加入我們的伺服器！</p>
        <a href="{{ oauth_url }}" class="btn">
            <img src="https://cdn.discordapp.com/embed/avatars/0.png" style="width: 24px; height: 24px; vertical-align: middle; margin-right: 8px; border-radius: 50%;">
            透過 Discord 加入
        </a>
        {% endif %}
    </div>
</body>
</html>
"""

class OAuthCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.oauth_sessions = {}  # 存儲 OAuth state 和 user_id 的對應
        self.invite_link = os.getenv('DISCORD_INVITE_LINK', '')
        
        # 從 .env 讀取 OAuth 設定
        self.client_id = os.getenv('DISCORD_CLIENT_ID', '')
        self.client_secret = os.getenv('DISCORD_CLIENT_SECRET', '')
        self.redirect_uri = "https://yokaro.wayna1015.ccwu.cc/"
        
        # 如果沒有設定 invite link，嘗試從 bot 建立
        if not self.invite_link and bot.application_id:
            self.invite_link = f"https://discord.com/oauth2/authorize?client_id={bot.application_id}&permissions=8&scope=bot"
    
    @commands.command(name='oauth', aliases=['加入'])
    async def oauth_command(self, ctx):
        """顯示 OAuth 加入伺服器面板"""
        # 建立 OAuth URL
        state = secrets.token_urlsafe(16)
        self.oauth_sessions[state] = {
            'user_id': ctx.author.id,
            'timestamp': datetime.now().timestamp()
        }
        
        # Discord OAuth2 URL
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'identify guilds.join',
            'state': state
        }
        oauth_url = f"https://discord.com/oauth2/authorize?{urllib.parse.urlencode(params)}"
        
        # 建立嵌入訊息
        embed = discord.Embed(
            title="🔐 加入伺服器",
            description="點擊下方按鈕，透過 Discord OAuth2 授權加入伺服器！",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        embed.add_field(
            name="📋 使用方式",
            value="1. 點擊下方連結\n2. 在 Discord 授權頁面點擊「授權」\n3. 系統會自動將你加入伺服器",
            inline=False
        )
        embed.set_footer(text="Yokaro OAuth System")
        
        # 建立按鈕
        view = OAuthView(oauth_url)
        await ctx.send(embed=embed, view=view)
    
    @app_route('/oauth/callback')
    def oauth_callback(self):
        """OAuth2 callback 處理"""
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if error:
            return render_template_string(OAUTH_HTML_TEMPLATE, 
                error=f"授權失敗：{error}",
                success=None,
                oauth_url=None)
        
        if not code or not state:
            return render_template_string(OAUTH_HTML_TEMPLATE, 
                error="無效的授權請求",
                success=None,
                oauth_url=None)
        
        # 驗證 state
        if state not in self.oauth_sessions:
            return render_template_string(OAUTH_HTML_TEMPLATE, 
                error="無效的 session",
                success=None,
                oauth_url=None)
        
        session_data = self.oauth_sessions[state]
        user_id = session_data['user_id']
        
        # 清理已使用的 session
        del self.oauth_sessions[state]
        
        try:
            # 用 code 換 access_token
            token_data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': self.redirect_uri,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            token_resp = requests.post(
                'https://discord.com/api/v9/oauth2/token',
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if token_resp.status_code != 200:
                return render_template_string(OAUTH_HTML_TEMPLATE, 
                    error="Token 交換失敗",
                    success=None,
                    oauth_url=None)
            
            access_token = token_resp.json().get('access_token')
            
            # 取得用戶資訊
            user_resp = requests.get(
                'https://discord.com/api/v9/users/@me',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if user_resp.status_code != 200:
                return render_template_string(OAUTH_HTML_TEMPLATE, 
                    error="無法取得用戶資訊",
                    success=None,
                    oauth_url=None)
            
            user_data = user_resp.json()
            authorized_user_id = user_data.get('id')
            
            # 驗證用戶 ID 是否匹配
            if str(authorized_user_id) != str(user_id):
                return render_template_string(OAUTH_HTML_TEMPLATE, 
                    error="用戶驗證失敗",
                    success=None,
                    oauth_url=None)
            
            # 異步加入伺服器
            asyncio.run_coroutine_threadsafe(
                self._add_user_to_guild(authorized_user_id, access_token),
                self.bot.loop
            )
            
            return render_template_string(OAUTH_HTML_TEMPLATE, 
                error=None,
                success="授權成功！正在將你加入伺服器...",
                oauth_url=None)
            
        except Exception as e:
            print(f"❌ [OAuth] Callback 錯誤: {e}")
            import traceback
            traceback.print_exc()
            return render_template_string(OAUTH_HTML_TEMPLATE, 
                error=f"處理授權時發生錯誤：{str(e)}",
                success=None,
                oauth_url=None)
    
    async def _add_user_to_guild(self, user_id: str, access_token: str):
        """將用戶加入伺服器"""
        try:
            # 取得第一個可用的伺服器
            if not self.bot.guilds:
                print("❌ [OAuth] 沒有可用的伺服器")
                return
            
            guild = self.bot.guilds[0]
            
            # 使用 Discord API 加入用戶到伺服器
            url = f"https://discord.com/api/v9/guilds/{guild.id}/members/{user_id}"
            
            headers = {
                'Authorization': f'Bot {self.bot.http.token}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'access_token': access_token
            }
            
            response = requests.put(url, json=data, headers=headers)
            
            if response.status_code in [200, 201]:
                print(f"✅ [OAuth] 用戶 {user_id} 已成功加入伺服器 {guild.name}")
            elif response.status_code == 204:
                print(f"✅ [OAuth] 用戶 {user_id} 已經在伺服器中")
            else:
                print(f"❌ [OAuth] 加入伺服器失敗: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ [OAuth] 加入伺服器時發生錯誤: {e}")
            import traceback
            traceback.print_exc()


class OAuthView(discord.ui.View):
    """OAuth 加入按鈕"""
    
    def __init__(self, oauth_url: str):
        super().__init__(timeout=300)  # 5 分鐘超時
        self.oauth_url = oauth_url
    
    @discord.ui.button(label="🔐 透過 Discord 加入", style=discord.ButtonStyle.primary, emoji="✨")
    async def oauth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """點擊按鈕開啟 OAuth 授權"""
        await interaction.response.send_message(
            f"點擊此連結開始授權：\n{self.oauth_url}",
            ephemeral=True
        )


# 將 OAuth callback 路由添加到 webpanel
def setup_oauth_routes(webpanel_cog):
    """設定 OAuth 路由（需要在 webpanel 啟動後呼叫）"""
    from cogs.webpanel import app
    
    @app.route('/oauth/callback')
    def oauth_callback_route():
        return webpanel_cog.oauth_callback()
    
    @app.route('/oauth')
    def oauth_page():
        state = request.args.get('state')
        if not state or state not in webpanel_cog.oauth_sessions:
            return redirect('/oauth/callback?error=invalid_state')
        
        # 建立 OAuth URL
        params = {
            'client_id': webpanel_cog.client_id,
            'redirect_uri': webpanel_cog.redirect_uri,
            'response_type': 'code',
            'scope': 'identify guilds.join',
            'state': state
        }
        oauth_url = f"https://discord.com/oauth2/authorize?{urllib.parse.urlencode(params)}"
        
        return render_template_string(OAUTH_HTML_TEMPLATE, 
            error=None, 
            success=None, 
            oauth_url=oauth_url)


async def setup(bot):
    await bot.add_cog(OAuthCog(bot))