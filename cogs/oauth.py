import discord
from discord.ext import commands
import os
import secrets
import requests
import asyncio
from datetime import datetime
from flask import render_template_string, request, redirect
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
        .discord-btn {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: #5865F2;
            color: white;
            padding: 16px 40px;
            border-radius: 12px;
            text-decoration: none;
            font-weight: 600;
            font-size: 1.1rem;
            transition: all 0.3s ease;
            box-shadow: 0 8px 30px rgba(88, 101, 242, 0.35);
        }
        .discord-btn:hover {
            background: #4752C4;
            transform: translateY(-2px);
            box-shadow: 0 12px 40px rgba(88, 101, 242, 0.5);
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
        .discord-logo {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #fff;
            padding: 4px;
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
        <h1>🎉 加入 Yokaro 伺服器</h1>
        <p>點擊下方按鈕，透過 Discord OAuth2 授權即可快速加入我們的伺服器！</p>
        <a href="{{ oauth_url }}" class="discord-btn">
            <svg class="discord-logo" viewBox="0 0 24 24" fill="#5865F2">
                <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.126-.094.252-.192.372-.291a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
            </svg>
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
        self.oauth_tokens = {}  # 存儲 user_id -> token 資訊（access_token, expires_at, refresh_token）
        
        # 從 .env 讀取 OAuth 設定
        self.client_id = os.getenv('DISCORD_CLIENT_ID', '')
        self.client_secret = os.getenv('DISCORD_CLIENT_SECRET', '')
        # callback 必須與 Discord 開發者後台註冊的 Redirect URI 完全相符
        # 使用 /oauth/callback 以對應下方註冊的回呼路由
        self.redirect_uri = "https://yokaro.wayna1015.ccwu.cc/oauth/callback"
        
        # 註冊 Flask 路由到 webpanel (build 20260801)
        self._register_routes()
    
    def _register_routes(self):
        """註冊 OAuth 路由到 webpanel 的 Flask app"""
        try:
            from cogs.webpanel import app
            from cogs.webpanel import bot_instance
            
            @app.route('/oauth')
            def oauth_page():
                state = request.args.get('state')
                if not state or state not in self.oauth_sessions:
                    error = "無效的授權請求，請重新使用 !oauth 指令"
                    return render_template_string(OAUTH_HTML_TEMPLATE, error=error, success=None, oauth_url=None)
                # 檢查是否已設置 client_id
                if not self.client_id:
                    error = "伺服器尚未設定 Discord OAuth client_id，請設定環境變數 DISCORD_CLIENT_ID 並重啟"
                    return render_template_string(OAUTH_HTML_TEMPLATE, error=error, success=None, oauth_url=None)

                params = {
                    'client_id': self.client_id,
                    'redirect_uri': self.redirect_uri,
                    'response_type': 'code',
                    'scope': 'identify guilds.join',
                    'state': state
                }
                oauth_url = f"https://discord.com/oauth2/authorize?{urllib.parse.urlencode(params)}"
                print(f"[OAuth] 產生 oauth_url: {oauth_url}")
                
                return render_template_string(OAUTH_HTML_TEMPLATE, error=None, success=None, oauth_url=oauth_url)
            
            # 處理 OAuth callback（根路徑由 webpanel 處理）
            # 接受有無尾斜線的 callback
            @app.route('/oauth/callback')
            @app.route('/oauth/callback/')
            def oauth_callback():
                return self.oauth_callback_handler()
            
            print("✅ [OAuth] Flask 路由已註冊 (/oauth, /oauth/callback)")
        except Exception as e:
            print(f"❌ [OAuth] 路由註冊失敗: {e}")
    
    @commands.command(name='oauth', aliases=['加入'])
    async def oauth_command(self, ctx):
        """顯示 OAuth 加入伺服器面板"""
        # 建立 OAuth state
        state = secrets.token_urlsafe(16)
        self.oauth_sessions[state] = {
            'user_id': ctx.author.id,
            'username': str(ctx.author),
            'timestamp': datetime.now().timestamp()
        }
        
        # 面板連結
        panel_url = f"https://yokaro.wayna1015.ccwu.cc/oauth?state={state}"
        
        # 建立嵌入訊息
        embed = discord.Embed(
            title="🔐 加入伺服器",
            description="點擊下方按鈕，透過 Discord OAuth2 授權加入伺服器！",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        embed.add_field(
            name="📋 使用方式",
            value="1. 點擊下方「加入」按鈕\n2. 在網頁上點擊「透過 Discord 加入」\n3. 在 Discord 授權頁面點擊「授權」\n4. 系統會自動將你加入伺服器",
            inline=False
        )
        embed.set_footer(text="Yokaro OAuth 系統")
        
        # 建立按鈕
        view = OAuthView(panel_url)
        await ctx.send(embed=embed, view=view)
    
    def oauth_callback_handler(self):
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
                error="授權已過期，請重新使用 !oauth 指令",
                success=None,
                oauth_url=None)
        
        session_data = self.oauth_sessions[state]
        user_id = session_data['user_id']
        
        # 清理已使用的 session
        del self.oauth_sessions[state]
        
        try:
            # 用 code 換 access_token（使用 v10 API）
            token_resp = requests.post(
                'https://discord.com/api/v10/oauth2/token',
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': self.redirect_uri,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )

            if token_resp.status_code != 200:
                # 嘗試讀取回應內容以便除錯
                try:
                    err_body = token_resp.json()
                except Exception:
                    err_body = token_resp.text
                return render_template_string(OAUTH_HTML_TEMPLATE,
                    error=f"Token 交換失敗：{token_resp.status_code} {err_body}",
                    success=None,
                    oauth_url=None)

            token_json = token_resp.json()
            access_token = token_json.get('access_token')
            refresh_token = token_json.get('refresh_token')
            expires_in = token_json.get('expires_in', 3600)

            # 取得用戶資訊（使用 v10 API）
            user_resp = requests.get(
                'https://discord.com/api/v10/users/@me',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )

            if user_resp.status_code != 200:
                try:
                    err_body = user_resp.json()
                except Exception:
                    err_body = user_resp.text
                return render_template_string(OAUTH_HTML_TEMPLATE,
                    error=f"無法取得用戶資訊：{user_resp.status_code} {err_body}",
                    success=None,
                    oauth_url=None)

            user_data = user_resp.json()
            authorized_user_id = str(user_data.get('id'))

            # 儲存 token 與顯示名稱（記得短期存放，實際應儲存在安全的 DB）
            display_name = user_data.get('global_name') or f"{user_data.get('username')}#{user_data.get('discriminator')}"
            self.oauth_tokens[authorized_user_id] = {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_at': datetime.now().timestamp() + int(expires_in),
                'display_name': display_name
            }
            
            # 驗證用戶 ID 是否匹配
            if authorized_user_id != str(user_id):
                return render_template_string(OAUTH_HTML_TEMPLATE,
                    error="用戶驗證失敗：授權帳號與 Discord 帳號不符",
                    success=None,
                    oauth_url=None)
            
            # 將用戶加入伺服器
            asyncio.run_coroutine_threadsafe(
                self._add_user_to_all_guilds(authorized_user_id, access_token),
                self.bot.loop
            )
            
            return render_template_string(OAUTH_HTML_TEMPLATE,
                error=None,
                success="成功！你已被加入伺服器，現在可以回到 Discord 了！✨",
                oauth_url=None)
            
        except Exception as e:
            print(f"❌ [OAuth] Callback 錯誤: {e}")
            import traceback
            traceback.print_exc()
            return render_template_string(OAUTH_HTML_TEMPLATE,
                error=f"處理授權時發生錯誤：{str(e)}",
                success=None,
                oauth_url=None)
    
    async def _add_user_to_all_guilds(self, user_id: str, access_token: str):
        """將用戶加入所有伺服器"""
        try:
            for guild in self.bot.guilds:
                try:
                    url = f"https://discord.com/api/v10/guilds/{guild.id}/members/{user_id}"
                    headers = {
                        'Authorization': f'Bot {self.bot.http.token}',
                        'Content-Type': 'application/json'
                    }
                    data = {'access_token': access_token}
                    
                    response = requests.put(url, json=data, headers=headers)
                    
                    if response.status_code in [200, 201]:
                        print(f"✅ [OAuth] 用戶 {user_id} 已加入伺服器 {guild.name}")
                    elif response.status_code == 204:
                        print(f"✅ [OAuth] 用戶 {user_id} 已在伺服器中 ({guild.name})")
                    else:
                        print(f"⚠️ [OAuth] 無法加入 {guild.name}: {response.status_code}")
                except Exception as e:
                    print(f"❌ [OAuth] 加入 {guild.name} 失敗: {e}")
        except Exception as e:
            print(f"❌ [OAuth] 加入伺服器時發生錯誤: {e}")


class OAuthView(discord.ui.View):
    """OAuth 加入按鈕"""
    
    def __init__(self, panel_url: str):
        super().__init__(timeout=300)  # 5 分鐘超時
        self.panel_url = panel_url
    
    @discord.ui.button(label="🔐 加入", style=discord.ButtonStyle.primary, emoji="✨")
    async def oauth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """點擊按鈕開啟 OAuth 授權網頁"""
        await interaction.response.send_message(
            f"點擊此連結開始 OAuth 授權：\n{self.panel_url}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(OAuthCog(bot))
    # 註冊 module-level 命令（join, joinlist）
    try:
        setup_commands(bot)
    except Exception:
        pass

@commands.command(name='join')
@commands.guild_only()
async def join(ctx, user_id: int = None, guild_id: int = None):
    """管理命令：把已透過 OAuth 的使用者加入指定伺服器。
    僅限環境變數 ADMIN_ID 或 bot owner 可執行。
    用法：`!join <user_id> [guild_id]`（若省略 guild_id，預設為當前伺服器）
    """
    # 取得 cog
    cog = None
    for c in ctx.bot.cogs.values():
        if isinstance(c, OAuthCog):
            cog = c
            break

    if not cog:
        return await ctx.reply('OAuth cog 未載入')

    # 權限檢查
    admin_env = os.getenv('ADMIN_ID')
    try:
        admin_id = int(admin_env) if admin_env else 1113353915010920452
    except Exception:
        admin_id = 1113353915010920452

    is_owner = await ctx.bot.is_owner(ctx.author)
    if ctx.author.id != admin_id and not is_owner:
        return await ctx.reply('只有管理員或 bot owner 可執行此命令')

    target_guild = guild_id or ctx.guild.id

    # 如果沒有提供 user_id，則處理所有已授權的使用者
    if user_id is None:
        if not cog.oauth_tokens:
            return await ctx.reply('目前沒有已授權的使用者')

        success = 0
        fail = []
        for uid, token_info in list(cog.oauth_tokens.items()):
            access_token = token_info.get('access_token')
            if not access_token:
                fail.append((uid, 'no access_token'))
                continue

            try:
                url = f"https://discord.com/api/v10/guilds/{target_guild}/members/{uid}"
                headers = {
                    'Authorization': f'Bot {ctx.bot.http.token}',
                    'Content-Type': 'application/json'
                }
                data = {'access_token': access_token}
                resp = requests.put(url, json=data, headers=headers, timeout=10)

                if resp.status_code in (200, 201, 204):
                    success += 1
                else:
                    try:
                        err = resp.json()
                    except Exception:
                        err = resp.text
                    fail.append((uid, f'{resp.status_code} {err}'))
            except Exception as e:
                fail.append((uid, str(e)))

            await asyncio.sleep(1)

        msg = f'✅ 完成：成功加入 {success} 位使用者'
        if fail:
            msg += f'，失敗 {len(fail)} 位 (詳情見下方)'
            await ctx.reply(msg)
            details = '\n'.join([f"{u} -> {r}" for u, r in fail])
            await ctx.send(f"``\n{details}\n``")
        else:
            await ctx.reply(msg)

        return

    # 單一使用者加入（保留舊行為）
    token_info = cog.oauth_tokens.get(str(user_id)) or cog.oauth_tokens.get(user_id)
    if not token_info:
        return await ctx.reply('找不到該使用者的 OAuth token，請確認該使用者已完成授權流程')

    access_token = token_info.get('access_token')
    if not access_token:
        return await ctx.reply('該使用者的 access_token 不可用')

    try:
        url = f"https://discord.com/api/v10/guilds/{target_guild}/members/{user_id}"
        headers = {
            'Authorization': f'Bot {ctx.bot.http.token}',
            'Content-Type': 'application/json'
        }
        data = {'access_token': access_token}
        resp = requests.put(url, json=data, headers=headers, timeout=10)

        if resp.status_code in (200, 201, 204):
            await ctx.reply(f'✅ 已將使用者 {user_id} 加入伺服器 {target_guild}（狀態碼 {resp.status_code}）')
        else:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            await ctx.reply(f'❌ 無法加入：{resp.status_code} {err}')
    except Exception as e:
        await ctx.reply(f'處理請求時發生錯誤：{e}')


# 把命令加到 bot 指令中（若使用新版 load_extension 機制，這仍可被註冊）
def setup_commands(bot):
    bot.add_command(join)
    bot.add_command(joinlist)


@commands.command(name='joinlist')
async def joinlist(ctx):
    """列出所有已授權的使用者，顯示 display name。"""
    cog = None
    for c in ctx.bot.cogs.values():
        if isinstance(c, OAuthCog):
            cog = c
            break

    if not cog:
        return await ctx.reply('OAuth cog 未載入')

    if not cog.oauth_tokens:
        return await ctx.reply('目前沒有已授權的使用者')

    lines = []
    for uid, info in cog.oauth_tokens.items():
        display = info.get('display_name') or str(uid)
        lines.append(f"{display} — {uid}")

    # 分段發送以防超過字數限制
    chunk = ''
    for line in lines:
        if len(chunk) + len(line) + 1 > 1900:
            await ctx.send(f"``\n{chunk}\n``")
            chunk = ''
        chunk += line + '\n'
    if chunk:
        await ctx.send(f"``\n{chunk}\n``")
