import asyncio
import io
import random
import re
import urllib.parse
from typing import Optional

import aiohttp
import discord
import requests
from bs4 import BeautifulSoup
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='weather', aliases=['天氣'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def weather(self, ctx, *, city: str):
        """查詢天氣資訊 (使用 wttr.in)"""
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{urllib.parse.quote(city)}?format=3"
            async with session.get(url) as response:
                if response.status == 200:
                    text = await response.text()
                    await ctx.send(f"🌦️ **{city}** 的天氣訊號：\n{text}")
                else:
                    await ctx.send("嗷～氣象衛星斷線了，查不到那裡的天氣。")

    @commands.hybrid_command(name='wiki', aliases=['維基', '查'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def wiki(self, ctx, *, query: str):
        """搜尋維基百科 (使用官方 API)"""
        await ctx.defer()
        async with aiohttp.ClientSession() as session:
            # 1. 搜尋條目
            search_url = f"https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json"
            async with session.get(search_url) as response:
                if response.status != 200:
                    return await ctx.send("嗷嗷嗷～連接維基百科失敗！")
                
                search_data = await response.json()
                results = search_data.get('query', {}).get('search', [])
                if not results:
                    return await ctx.send("嗷～這在洛洛的資料庫裡找不到喔！")
                
                title = results[0]['title']
                pageid = results[0]['pageid']

            # 2. 獲取摘要與縮圖
            detail_url = (
                f"https://zh.wikipedia.org/w/api.php?action=query&prop=extracts|pageimages"
                f"&exintro&explaintext&exchars=300&piprop=thumbnail&pithumbsize=500"
                f"&titles={urllib.parse.quote(title)}&format=json"
            )
            async with session.get(detail_url) as response:
                if response.status == 200:
                    detail_data = await response.json()
                    pages = detail_data.get('query', {}).get('pages', {})
                    page_info = pages.get(str(pageid)) or next(iter(pages.values()))
                    
                    summary = page_info.get('extract', "找不到相關摘要。")
                    thumbnail = page_info.get('thumbnail', {}).get('source')
                    url = f"https://zh.wikipedia.org/wiki/{urllib.parse.quote(title)}"

                    embed = discord.Embed(title=title, description=summary, url=url, color=0x3498db)
                    if thumbnail:
                        embed.set_image(url=thumbnail)
                    embed.set_footer(text="來源：維基百科 (官方 API)")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("嗷～獲取詳細資訊時迷路了！")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(name='stock', aliases=['股價'])
    async def stock(self, ctx, symbol: str):
        """查詢美股/台股即時股價 (Yahoo Finance 強化版)"""
        await ctx.defer()
        symbol = symbol.upper()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        url = f"https://finance.yahoo.com/quote/{symbol}"
        
        def fetch_stock():
            return requests.get(url, headers=headers, timeout=10)
            
        try:
            response = await asyncio.to_thread(fetch_stock)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 抓取價格 (多重備援)
                price = "未知"
                for field in ['regularMarketPrice', 'postMarketPrice']:
                    price_elem = soup.find('fin-streamer', {'data-field': field, 'data-symbol': symbol})
                    if price_elem and price_elem.text:
                        price = price_elem.text
                        break
                
                # 抓取漲跌
                change = "未知"
                change_elem = soup.find('fin-streamer', {'data-field': 'regularMarketChangePercent', 'data-symbol': symbol})
                if change_elem: change = change_elem.text.strip('()')

                # 抓取貨幣
                currency = ""
                curr_elem = soup.find('span', string=re.compile(r'Currency in')) if 're' in globals() else None
                #  fallback if re not loaded or not found
                if not currency:
                    meta_curr = soup.find('meta', {'itemprop': 'currency'})
                    currency = meta_curr['content'] if meta_curr else ""

                embed = discord.Embed(title=f"💹 股市資訊: {symbol}", color=0x2ecc71, url=url)
                embed.add_field(name="目前價格", value=f"**{price}** {currency}", inline=True)
                embed.add_field(name="今日漲跌", value=f"**{change}**", inline=True)
                
                if ".TW" not in symbol and symbol.isdigit():
                    embed.set_footer(text="💡 提示：查詢台股請輸入代號+ .TW (例如 2330.TW)")
                else:
                    embed.set_footer(text="來源：Yahoo Finance")
                
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"嗷～找不到代號 `{symbol}` 的資料。請檢查輸入是否正確！")
        except Exception as e:
            print(f"Stock error: {e}")
            await ctx.send("嗷嗷嗷～連接股市衛星時發生意外錯誤！可能是網路不穩。")

    def _load_font(self, size: int):
        font_candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in font_candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    async def _build_author_card(self, avatar_bytes: Optional[bytes]):
        width, height = 1400, 800
        card = Image.new("RGBA", (width, height), (20, 24, 38, 255))
        draw = ImageDraw.Draw(card)

        rng = random.Random()
        color_a = (rng.randint(20, 70), rng.randint(30, 120), rng.randint(120, 235))
        color_b = (rng.randint(70, 170), rng.randint(30, 90), rng.randint(40, 120))

        for y in range(height):
            t = y / max(height - 1, 1)
            r = int(color_a[0] * (1 - t) + color_b[0] * t)
            g = int(color_a[1] * (1 - t) + color_b[1] * t)
            b = int(color_a[2] * (1 - t) + color_b[2] * t)
            draw.line((0, y, width, y), fill=(r, g, b, 255))

        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse((-220, -200, 900, 700), fill=(255, 255, 255, 45))
        glow_draw.ellipse((900, 90, 1550, 900), fill=(255, 255, 255, 30))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=42))
        card.alpha_composite(glow)

        panel = Image.new("RGBA", (1240, 660), (255, 255, 255, 16))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle((0, 0, 1239, 659), radius=40, fill=(255, 255, 255, 18), outline=(255, 255, 255, 70), width=3)
        card.alpha_composite(panel, (80, 70))

        accent = Image.new("RGBA", (320, 320), (0, 0, 0, 0))
        accent_draw = ImageDraw.Draw(accent)
        accent_draw.ellipse((0, 0, 319, 319), fill=(255, 255, 255, 22))
        accent = accent.filter(ImageFilter.GaussianBlur(radius=16))
        card.alpha_composite(accent, (90, 190))

        if avatar_bytes:
            try:
                avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                avatar = ImageOps.fit(avatar, (320, 320), method=Image.LANCZOS)
            except Exception:
                avatar = Image.new("RGBA", (320, 320), (70, 80, 95, 255))
        else:
            avatar = Image.new("RGBA", (320, 320), (70, 80, 95, 255))

        avatar_mask = Image.new("L", (320, 320), 0)
        avatar_mask_draw = ImageDraw.Draw(avatar_mask)
        avatar_mask_draw.ellipse((0, 0, 319, 319), fill=255)
        avatar_circle = Image.new("RGBA", (320, 320), (0, 0, 0, 0))
        avatar_circle.paste(avatar, (0, 0), avatar_mask)
        card.alpha_composite(avatar_circle, (90, 190))

        border = Image.new("RGBA", (332, 332), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border)
        border_draw.ellipse((0, 0, 331, 331), outline=(255, 255, 255, 130), width=6)
        card.alpha_composite(border, (84, 184))

        title_font = self._load_font(34)
        name_font = self._load_font(72)
        subtitle_font = self._load_font(30)
        body_font = self._load_font(24)

        draw = ImageDraw.Draw(card)
        draw.text((500, 210), "Bacon Lin", font=name_font, fill=(255, 255, 255, 255))
        draw.text((500, 295), "國中生｜熱愛研究程式", font=subtitle_font, fill=(226, 236, 255, 255))
        draw.text((500, 345), "Python / C++ / Minecraft 伺服器插件開發中", font=body_font, fill=(214, 224, 255, 240))
        draw.text((500, 385), "目前比較忙，但會持續把有趣的作品與功能做出來。", font=body_font, fill=(214, 224, 255, 240))

        badge = Image.new("RGBA", (260, 54), (255, 255, 255, 16))
        badge_draw = ImageDraw.Draw(badge)
        badge_draw.rounded_rectangle((0, 0, 259, 53), radius=27, fill=(255, 255, 255, 20), outline=(255, 255, 255, 80), width=2)
        draw.text((500, 150), "作者介紹", font=title_font, fill=(255, 255, 255, 230))
        card.alpha_composite(badge, (500, 150))

        buffer = io.BytesIO()
        card.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(name='作者介紹', aliases=['作者', 'about'])
    async def author_intro(self, ctx):
        """展示作者介紹名片（支援斜線與前綴指令）"""
        await ctx.defer()

        target_user_id = 1113353915010920452
        avatar_bytes = None
        try:
            user = await self.bot.fetch_user(target_user_id)
            if user and user.display_avatar:
                avatar_url = user.display_avatar.with_size(512).url
                async with aiohttp.ClientSession() as session:
                    async with session.get(avatar_url) as response:
                        if response.status == 200:
                            avatar_bytes = await response.read()
        except Exception:
            avatar_bytes = None

        card_buffer = await self._build_author_card(avatar_bytes)
        await ctx.send("這是我的作者名片～", file=discord.File(card_buffer, filename="author_card.png"))

async def setup(bot):
    await bot.add_cog(InfoCog(bot))
