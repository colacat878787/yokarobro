import discord
from discord.ext import commands
import asyncio
import aiohttp
import os
from datetime import datetime

class ScreenshotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.screenshot_dir = "screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)
    
    @commands.command(name='截圖', aliases=['screenshot', 'ss'])
    async def screenshot_webpage(self, ctx, url: str):
        """截取網頁截圖
        
        使用方式：
        !截圖 <網址>
        !screenshot <網址>
        !ss <網址>
        """
        # 檢查 URL 格式
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # 發送處理中訊息
        status_msg = await ctx.send("📸 正在截取網頁截圖，請稍候...")
        
        try:
            # 使用外部截圖 API (例如: screenshot-api.com 或類似的服務)
            # 這裡使用一個免費的截圖 API 範例
            screenshot_url = f"https://api.screenshotone.com/take"
            
            params = {
                'url': url,
                'viewport_width': 1920,
                'viewport_height': 1080,
                'device_scale_factor': 1,
                'format': 'png',
                'block_ads': 'true',
                'block_cookie_banners': 'true',
                'block_banners': 'true',
                'block_trackers': 'true',
                'delay': 0,
                'timeout': 30
            }
            
            # 如果有的話，使用 API key
            api_key = os.getenv('SCREENSHOT_API_KEY')
            if api_key:
                params['access_key'] = api_key
            
            async with aiohttp.ClientSession() as session:
                async with session.get(screenshot_url, params=params, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        # 讀取圖片資料
                        image_data = await response.read()
                        
                        # 儲存截圖
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"screenshot_{timestamp}.png"
                        filepath = os.path.join(self.screenshot_dir, filename)
                        
                        with open(filepath, 'wb') as f:
                            f.write(image_data)
                        
                        # 建立嵌入訊息
                        embed = discord.Embed(
                            title="📸 網頁截圖",
                            description=f"網址：{url}",
                            color=0x3498db,
                            timestamp=datetime.now()
                        )
                        embed.set_image(url=f"attachment://{filename}")
                        embed.set_footer(text=f"截圖時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        # 發送截圖
                        await status_msg.edit(content=None, embed=embed, attachments=[discord.File(filepath, filename=filename)])
                        
                        # 清理舊截圖（可選）
                        await self._cleanup_old_screenshots()
                    else:
                        await status_msg.edit(content=f"❌ 截圖失敗：API 返回錯誤 (狀態碼: {response.status})")
        
        except asyncio.TimeoutError:
            await status_msg.edit(content="❌ 截圖逾時：網頁載入時間過長")
        except Exception as e:
            await status_msg.edit(content=f"❌ 截圖失敗：{str(e)}")
    
    async def _cleanup_old_screenshots(self, max_files=50):
        """清理舊的截圖檔案"""
        try:
            files = sorted(os.listdir(self.screenshot_dir), key=lambda x: os.path.getmtime(os.path.join(self.screenshot_dir, x)))
            if len(files) > max_files:
                for old_file in files[:-max_files]:
                    filepath = os.path.join(self.screenshot_dir, old_file)
                    if os.path.exists(filepath):
                        os.remove(filepath)
        except:
            pass


async def setup(bot):
    await bot.add_cog(ScreenshotCog(bot))