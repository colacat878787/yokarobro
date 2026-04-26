import discord
from discord.ext import commands
import asyncio
import subprocess
import os
import secrets
import threading
from flask import Flask, render_template_string

# ── 大總裁專屬設定 ──
ADMIN_IDS = [1113353915010920452, 501251225715474433]

app = Flask(__name__)
panel_token = ""

@app.route("/")
def index():
    return f"<h1>Yokaro 大總裁專屬後台</h1><p>目前狀態: 正常運作中</p><p>管理員 Token: {panel_token}</p>"

class WebPanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tunnel_process = None
        self.flask_thread = None

    def run_flask(self):
        app.run(port=5000, debug=False, use_reloader=False)

    @commands.command(name='webpanel')
    async def open_panel(self, ctx):
        if ctx.author.id not in ADMIN_IDS:
            return await ctx.send("❌ 權限不足。此指令僅限「大總裁」使用。")

        if self.tunnel_process:
            return await ctx.send("⚠️ 後台網址已在運行中！請先點擊「立即註銷」或等待過期。")

        global panel_token
        panel_token = secrets.token_urlsafe(16)
        
        # 啟動 Flask (如果在運行中就跳過)
        if not self.flask_thread:
            self.flask_thread = threading.Thread(target=self.run_flask, daemon=True)
            self.flask_thread.start()

        await ctx.send("📡 **正在透過 Cloudflare 安全隧道建立連線...**")
        
        # 啟動 Cloudflared TryCloudflare
        try:
            self.tunnel_process = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", "http://localhost:5000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # 抓取網址
            url = ""
            for _ in range(20): # 等待最多 10 秒
                await asyncio.sleep(0.5)
                line = self.tunnel_process.stdout.readline()
                if ".trycloudflare.com" in line:
                    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                    if match:
                        url = match.group(0)
                        break
            
            if url:
                embed = discord.Embed(title="🔐 優卡洛專屬管理後台", color=0x5865f2)
                embed.description = f"大總裁，後台網址已生成！\n\n**連結:** [{url}]({url})\n**後綴密碼:** `{panel_token}`\n\n此連結會在關閉後失效。"
                embed.set_footer(text="點擊下方按鈕可立即註銷網址")
                
                view = discord.ui.View()
                btn = discord.ui.Button(label="立即註銷網址", style=discord.ButtonStyle.danger)
                
                async def burn_callback(interaction):
                    await self.close_tunnel()
                    await interaction.response.edit_message(content="✅ **網址已銷毀，後台已關閉。**", embed=None, view=None)
                
                btn.callback = burn_callback
                view.add_item(btn)
                
                await ctx.send(embed=embed, view=view)
            else:
                await ctx.send("❌ 無法獲取隧道網址，請確認 `cloudflared` 已安裝。")
        except Exception as e:
            await ctx.send(f"❌ 啟動失敗: {e}")

    async def close_tunnel(self):
        if self.tunnel_process:
            self.tunnel_process.terminate()
            self.tunnel_process = None

    def cog_unload(self):
        if self.tunnel_process:
            self.tunnel_process.terminate()

import re # 補上 re
async def setup(bot):
    await bot.add_cog(WebPanelCog(bot))
