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
            # 使用多個備用截圖 API
            screenshot_data = await self._try_screenshot_apis(url)
            
            if screenshot_data:
                # 儲存截圖
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
                filepath = os.path.join(self.screenshot_dir, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(screenshot_data)
                
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
                
                # 清理舊截圖
                await self._cleanup_old_screenshots()
            else:
                await status_msg.edit(content="❌ 截圖失敗：所有 API 都無法使用")
        
        except asyncio.TimeoutError:
            await status_msg.edit(content="❌ 截圖逾時：網頁載入時間過長")
        except Exception as e:
            await status_msg.edit(content=f"❌ 截圖失敗：{str(e)}")
    
    async def _try_screenshot_apis(self, url: str) -> bytes:
        """嘗試多個截圖 API"""
        apis = [
            # 嘗試免費的截圖服務 (不需要 API key)
            lambda: self._screenshot_free_service(url),
            # API 1: 使用 screenshotapi.net (需要 API key)
            lambda: self._screenshot_api_net(url),
            # API 2: 使用 apiflash.com (需要 API key)
            lambda: self._screenshot_apiflash(url),
            # API 3: 使用 screenshot-one.com (需要 API key)
            lambda: self._screenshot_screenshotone(url),
        ]
        
        for api_func in apis:
            try:
                result = await api_func()
                if result:
                    return result
            except:
                continue
        
        return None
    
    async def _screenshot_free_service(self, url: str) -> bytes:
        """使用免費的截圖服務 (不需要 API key)"""
        # 使用 thum.io 免費截圖服務
        api_url = f"https://image.thum.io/get/width/1920/crop/800/noanimate/{url}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.read()
        return None
    
    async def _screenshot_api_net(self, url: str) -> bytes:
        """使用 screenshotapi.net"""
        api_key = os.getenv('SCREENSHOT_API_KEY')
        if not api_key:
            return None
        
        api_url = f"https://api.screenshotapi.net/capture"
        params = {
            'token': api_key,
            'url': url,
            'width': 1920,
            'height': 1080,
            'output': 'image',
            'format': 'png'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.read()
        return None
    
    async def _screenshot_apiflash(self, url: str) -> bytes:
        """使用 apiflash.com"""
        api_key = os.getenv('SCREENSHOT_API_KEY')
        if not api_key:
            return None
        
        api_url = "https://api.apiflash.com/v1/urltoimage"
        params = {
            'access_key': api_key,
            'url': url,
            'width': 1920,
            'height': 1080,
            'format': 'png'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.read()
        return None
    
    async def _screenshot_screenshotone(self, url: str) -> bytes:
        """使用 screenshot-one.com"""
        api_key = os.getenv('SCREENSHOT_API_KEY')
        if not api_key:
            return None
        
        api_url = "https://api.screenshotone.com/take"
        params = {
            'access_key': api_key,
            'url': url,
            'viewport_width': 1920,
            'viewport_height': 1080,
            'device_scale_factor': 1,
            'format': 'png',
            'block_ads': 'true',
            'block_cookie_banners': 'true'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.read()
        return None
    
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